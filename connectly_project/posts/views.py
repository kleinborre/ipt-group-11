from rest_framework import generics, permissions, status, serializers
from rest_framework.response import Response
from django.contrib.auth.models import User
from .models import Post, Comment, Like, Follow
from .serializers import UserSerializer, PostSerializer, CommentSerializer, LikeSerializer, FollowSerializer, UploadPhotoSerializer
from .permissions import IsOwnerOrAdmin, IsAdminOrReadOnly
from factories.post_factory import PostFactory
from factories.comment_factory import CommentFactory
from django.shortcuts import get_object_or_404
from django.db.models import Prefetch, Count, Q
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from singletons.logger_singleton import LoggerSingleton

# For Google OAuth
from dj_rest_auth.registration.views import SocialLoginView
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
import requests

# For Google Drive API
from googleapiclient.discovery import build
from google.oauth2 import service_account
from googleapiclient.http import MediaFileUpload
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import status
import os
import json
from datetime import datetime
import tempfile
from django.contrib.auth.hashers import make_password

# For Caching
from django.core.cache import cache

# ------------------- PAGE NUMBER ----------------------
class FeedPagination(PageNumberPagination):
    page_size = 2  # Number of items per page
    page_size_query_param = 'page_size'
    max_page_size = 3  # Optional: Limit max results per page

# -------------------- LOGGER --------------------------
logger = LoggerSingleton().get_logger()

# ------------------- CACHING CONFIGURATION ----------------------
CACHE_TIMEOUT = 300  # Cache timeout in seconds (5 minutes)

# ------------------ GOOGLE DRIVE API -------------------------

# Load Google Drive credentials
GOOGLE_DRIVE_CREDENTIALS = "C:/Users/STUDY MODE/Desktop/apt-api-group11/service_account.json"
GOOGLE_DRIVE_PARENT_FOLDER_ID = os.getenv("GOOGLE_DRIVE_PARENT_FOLDER_ID")

# Authenticate with Google Drive
def authenticate_google_drive():
    if not GOOGLE_DRIVE_CREDENTIALS:
        raise Exception("Google Drive credentials not found")

    # Load JSON from the file (this was the issue)
    try:
        with open(GOOGLE_DRIVE_CREDENTIALS, "r", encoding="utf-8") as f:
            creds_dict = json.load(f)
    except json.JSONDecodeError as e:
        raise Exception(f"Error loading Google Drive credentials: {e}")

    creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=['https://www.googleapis.com/auth/drive'])
    return build('drive', 'v3', credentials=creds)

# Upload file to Google Drive
def upload_to_google_drive(file_obj, username):
    drive_service = authenticate_google_drive()

    # Get file extension
    file_extension = file_obj.name.split('.')[-1]

    # Generate a unique filename: username-profile-photo-YYYYMMDD-HHMMSS.ext
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    new_filename = f"{username}-profile-photo-{timestamp}.{file_extension}"

    # Save in-memory file to a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_extension}") as temp_file:
        for chunk in file_obj.chunks():
            temp_file.write(chunk)
        temp_file_path = temp_file.name

    file_metadata = {
        'name': new_filename,  # Set new filename
        'parents': [GOOGLE_DRIVE_PARENT_FOLDER_ID]
    }

    media = MediaFileUpload(temp_file_path, mimetype=file_obj.content_type, resumable=True)
    file = drive_service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id"
    ).execute()

    return f"https://drive.google.com/file/d/{file['id']}/view"

# ------------------- USER VIEWS -----------------------
class UserCreateView(generics.CreateAPIView):
    """
    Allows only admin users to create new users.
    """
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAdminUser] 
class UserRetrieveUpdateDestroy(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or delete a user.
    Implements caching for performance optimization.
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAdminOrReadOnly]

    def get_object(self):
        user_id = self.kwargs["pk"]
        cache_key = f"user_{user_id}"
        cached_user = cache.get(cache_key)

        if cached_user:
            logger.info(f"Cache hit: Fetching user {user_id} from cache.")
            return User.objects.get(id=user_id)  # Ensure it's a QuerySet object

        logger.info(f"Cache miss: Fetching user {user_id} from database.")
        user = get_object_or_404(User, id=user_id)
        cache.set(cache_key, UserSerializer(user).data, CACHE_TIMEOUT)  # Serialize before caching
        logger.info(f"Cache set: Cached user {user_id}.")
        return user

    def perform_update(self, serializer):
        instance = self.get_object()
        serializer.save()

        # Invalidate cache on update
        cache.delete(f"user_{instance.id}")
        cache.delete("users_list")
        logger.info(f"Cache invalidated: User {instance.id} updated.")

    def perform_destroy(self, instance):
        super().perform_destroy(instance)

        # Invalidate cache on delete
        cache.delete(f"user_{instance.id}")
        cache.delete("users_list")
        logger.info(f"Cache invalidated: User {instance.id} deleted.")

class UserListView(generics.ListAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['id']
    search_fields = ['username', 'email']
    ordering_fields = ['id', 'username', 'email']
    pagination_class = FeedPagination

    def get_queryset(self):
        return User.objects.annotate(
            followers_count=Count('followers', distinct=True),
            following_count=Count('following', distinct=True)
        ).order_by('id')

    def list(self, request, *args, **kwargs):
        cache_key = f"users_list_page_{request.query_params.get('page', 1)}"
        cached_data = cache.get(cache_key)

        if cached_data:
            logger.info("Cache hit: Fetching paginated users list from cache.")
            return Response(cached_data, status=status.HTTP_200_OK)

        logger.info("Cache miss: Fetching users list from database.")
        queryset = self.get_queryset()
        paginated_queryset = self.paginate_queryset(queryset)

        response = self.get_paginated_response(UserSerializer(paginated_queryset, many=True).data)

        cache.set(cache_key, response.data, CACHE_TIMEOUT)
        logger.info("Cache set: Cached paginated users list.")

        return response

# -------------------- POST VIEWS --------------------
class PostListCreate(generics.ListCreateAPIView):
    queryset = Post.objects.all().order_by('-created_at')
    serializer_class = PostSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = FeedPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['id']
    search_fields = ['title', 'content', 'author__username']
    ordering_fields = ['id', 'created_at', 'title', 'content']

    def get_queryset(self):
        """
        Retrieves posts with caching. Returns QuerySet.
        """
        page_number = self.request.query_params.get("page", 1)
        cache_key = f"posts_list_page_{page_number}"
        cached_posts = cache.get(cache_key)

        if cached_posts:
            logger.info(f"Cache hit: Fetching posts page {page_number} from cache.")
            return Post.objects.filter(id__in=[post["id"] for post in cached_posts]).order_by('-created_at')

        logger.info(f"Cache miss: Fetching posts from database for page {page_number}.")
        queryset = Post.objects.all().order_by('-created_at')
        paginated_queryset = self.paginate_queryset(queryset)

        serialized_data = PostSerializer(paginated_queryset, many=True).data
        cache.set(cache_key, serialized_data, CACHE_TIMEOUT)
        logger.info(f"Cache set: Cached posts page {page_number}.")

        return queryset

    def list(self, request, *args, **kwargs):
        """
        Ensures paginated responses are cached.
        """
        page_number = request.query_params.get("page", 1)
        cache_key = f"posts_list_page_{page_number}"
        cached_data = cache.get(cache_key)

        if cached_data:
            logger.info(f"Cache hit: Returning cached paginated response for page {page_number}.")
            return Response(cached_data, status=status.HTTP_200_OK)

        response = super().list(request, *args, **kwargs)

        # Cache the paginated response
        cache.set(cache_key, response.data, CACHE_TIMEOUT)
        logger.info(f"Cache set: Cached paginated posts for page {page_number}.")

        return response

    def perform_create(self, serializer):
        """
        Handles post creation and cache invalidation.
        """
        data = self.request.data
        try:
            post = PostFactory.create_post(
                post_type=data['post_type'],
                title=data['title'],
                content=data.get('content', ''),
                metadata=data.get('metadata', {}),
                author=self.request.user
            )

            # Handle media files (images & videos)
            if 'image' in self.request.FILES:
                post.image = self.request.FILES['image']
            if 'video' in self.request.FILES:
                post.video = self.request.FILES['video']

            post.save()
            serializer.instance = post

            # **Manually clear post list cache**
            self.clear_post_cache()

            logger.info(f"Post created: '{post.title}' by {self.request.user.username}")

        except ValueError as e:
            logger.error(f"Post creation failed: {str(e)}")
            raise serializers.ValidationError(str(e))

    def clear_post_cache(self):
        """
        **Manually deletes cached post pages** (works with all cache backends).
        """
        logger.info("Clearing all cached post pages...")
        page = 1
        while True:
            cache_key = f"posts_list_page_{page}"
            if cache.get(cache_key):
                cache.delete(cache_key)
                logger.info(f"Cache deleted: {cache_key}")
            else:
                break  # Stop when no more pages exist
            page += 1

class PostRetrieveUpdateDestroy(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or delete a post.
    Implements caching for performance optimization.
    """
    queryset = Post.objects.all()
    serializer_class = PostSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrAdmin]

    def get_object(self):
        post_id = self.kwargs["pk"]
        cache_key = f"post_{post_id}"
        cached_post = cache.get(cache_key)

        if cached_post:
            logger.info(f"Cache hit: Fetching post {post_id} from cache.")
            return Post.objects.get(id=post_id)  # Ensure it's a QuerySet object

        logger.info(f"Cache miss: Fetching post {post_id} from database.")
        post = get_object_or_404(Post, id=post_id)
        cache.set(cache_key, PostSerializer(post).data, CACHE_TIMEOUT)  # Serialize before caching
        logger.info(f"Cache set: Cached post {post_id}.")
        return post

    def perform_update(self, serializer):
        instance = self.get_object()
        serializer.save()

        # Invalidate cache when a post is updated
        cache.delete(f"post_{instance.id}")
        cache.delete("posts_list")
        logger.info(f"Cache invalidated: Post {instance.id} updated.")

    def perform_destroy(self, instance):
        super().perform_destroy(instance)

        # Invalidate cache when a post is deleted
        cache.delete(f"post_{instance.id}")
        cache.delete("posts_list")
        logger.info(f"Cache invalidated: Post {instance.id} deleted.")

# -------------------- COMMENT VIEWS --------------------
class CommentListCreate(generics.ListCreateAPIView):
    """
    Lists all comments and allows authenticated users to create new comments.
    Caching implemented to improve performance.
    """
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['id']
    search_fields = ['content', 'author__username']
    ordering_fields = ['id', 'created_at', 'content']
    pagination_class = FeedPagination

    def get_queryset(self):
        cache_key = "comments_list"
        cached_comments = cache.get(cache_key)

        if cached_comments:
            logger.info("Cache hit: Fetching comments from cache.")
            return cached_comments

        logger.info("Cache miss: Fetching comments from database.")
        comments = Comment.objects.all().order_by('-created_at')
        cache.set(cache_key, comments, CACHE_TIMEOUT)
        logger.info("Cache set: Comments list cached.")
        return comments

    def perform_create(self, serializer):
        data = self.request.POST
        files = self.request.FILES

        try:
            comment = CommentFactory.create_comment(
                comment_type=data['comment_type'],
                content=data.get('content', ''),
                metadata=data.get('metadata', {}),
                author=self.request.user,
                post=Post.objects.get(id=data['post'])
            )

            # Only assign files if they exist to avoid NoneType errors
            if 'image' in files and files['image'] is not None:
                comment.image = files['image']
            if 'video' in files and files['video'] is not None:
                comment.video = files['video']

            comment.save()
            serializer.instance = comment

            # Invalidate cache when a new comment is added
            cache.delete("comments_list")
            logger.info(f"Cache invalidated: New comment added on post ID {comment.post.id}.")

            logger.info(f"Comment created on Post ID {comment.post.id} by {self.request.user.username}")

        except ValueError as e:
            logger.error(f"Comment creation failed: {str(e)}")
            raise serializers.ValidationError(str(e))
        
class CommentRetrieveUpdateDestroy(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or delete a comment.
    Implements caching for performance optimization.
    """
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrAdmin]

    def get_object(self):
        comment_id = self.kwargs["pk"]
        cache_key = f"comment_{comment_id}"
        cached_comment = cache.get(cache_key)

        if cached_comment:
            logger.info(f"Cache hit: Fetching comment {comment_id} from cache.")
            return Comment.objects.get(id=comment_id)  # Ensure it's a QuerySet object

        logger.info(f"Cache miss: Fetching comment {comment_id} from database.")
        comment = get_object_or_404(Comment, id=comment_id)
        cache.set(cache_key, CommentSerializer(comment).data, CACHE_TIMEOUT)  # Serialize before caching
        logger.info(f"Cache set: Cached comment {comment_id}.")
        return comment

    def perform_update(self, serializer):
        instance = self.get_object()
        serializer.save()

        # Invalidate cache on update
        cache.delete(f"comment_{instance.id}")
        cache.delete("comments_list")
        logger.info(f"Cache invalidated: Comment {instance.id} updated.")

    def perform_destroy(self, instance):
        super().perform_destroy(instance)

        # Invalidate cache on delete
        cache.delete(f"comment_{instance.id}")
        cache.delete("comments_list")
        logger.info(f"Cache invalidated: Comment {instance.id} deleted.")

# -------------------- COMMENT TRACKING VIEWS --------------------
class PostCommentDetail(generics.RetrieveAPIView):
    serializer_class = CommentSerializer

    def get_queryset(self):
        return Comment.objects.filter(post_id=self.kwargs['post_id'], id=self.kwargs['comment_id'])

class PostAllCommentsList(generics.ListAPIView):
    serializer_class = CommentSerializer

    def get_queryset(self):
        return Comment.objects.filter(post_id=self.kwargs['post_id'])

class AllCommentsList(generics.ListAPIView):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer

# -------------------- USER COMMENT TRACKING --------------------
class UserPostCommentDetail(generics.RetrieveAPIView):
    serializer_class = CommentSerializer
    lookup_field = "id"  # Use 'id' because 'comment_id' does not exist in the database

    def get_object(self):
        return get_object_or_404(
            Comment,
            author_id=self.kwargs['user_id'],
            post_id=self.kwargs['post_id'],
            id=self.kwargs['comment_id']  # Correct field name is 'id'
        )

class UserPostCommentsList(generics.ListAPIView):
    serializer_class = CommentSerializer

    def get_queryset(self):
        return Comment.objects.filter(author_id=self.kwargs['user_id'], post_id=self.kwargs['post_id'])

class UserAllCommentsList(generics.ListAPIView):
    serializer_class = CommentSerializer

    def get_queryset(self):
        return Comment.objects.filter(author_id=self.kwargs['user_id'])

# -------------------- USER POST TRACKING --------------------
class UserSpecificPost(generics.RetrieveAPIView):
    serializer_class = PostSerializer
    lookup_field = "id"  # Explicitly set lookup field to "id"

    def get_object(self):
        return get_object_or_404(
            Post,
            author_id=self.kwargs["user_id"],
            id=self.kwargs["post_id"]  # Ensure we use "id", not "post_id"
        )

class UserPostList(generics.ListAPIView):
    serializer_class = PostSerializer

    def get_queryset(self):
        return Post.objects.filter(author_id=self.kwargs['user_id'])

# -------------------- LIKE VIEWS --------------------
class LikePostView(generics.CreateAPIView):
    serializer_class = LikeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        post = Post.objects.get(id=kwargs.get("pk"))
        like, created = Like.objects.get_or_create(user=request.user, post=post)
        if not created:
            like.delete()
            return Response({"message": "Like removed"}, status=status.HTTP_200_OK)
        return Response({"message": "Post liked"}, status=status.HTTP_201_CREATED)

class LikeCommentView(generics.CreateAPIView):
    serializer_class = LikeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        comment = Comment.objects.get(id=kwargs.get("pk"))
        like, created = Like.objects.get_or_create(user=request.user, comment=comment)
        if not created:
            like.delete()
            return Response({"message": "Like removed"}, status=status.HTTP_200_OK)
        return Response({"message": "Comment liked"}, status=status.HTTP_201_CREATED)
    

# -------------------- GOOGLE OAUTH --------------------
class GoogleLogin(SocialLoginView):
    adapter_class = GoogleOAuth2Adapter

class ConvertTokenView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        access_token = request.data.get("access_token")
        if not access_token:
            return Response({"error": "Missing access token"}, status=400)

        # Verify and get user info from Google
        google_user_info_url = "https://www.googleapis.com/oauth2/v2/userinfo"
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(google_user_info_url, headers=headers)

        if response.status_code != 200:
            return Response({"error": "Invalid Google token"}, status=400)

        user_info = response.json()
        email = user_info.get("email")

        if not email:
            return Response({"error": "Unable to fetch email from Google"}, status=400)

        # Get or create user, assigning default password 'mmdc2025' if new
        user_model = get_user_model()
        user, created = user_model.objects.get_or_create(
            email=email, 
            defaults={"username": email.split("@")[0], "password": make_password("mmdc2025")}
        )

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        return Response({
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "email": email,
        })


# -------------------- FOLLOW VIEWS --------------------
class FollowUserView(generics.CreateAPIView):
    serializer_class = FollowSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        following_user = get_object_or_404(User, id=kwargs['user_id'])
        if request.user == following_user:
            return Response({"error": "You cannot follow yourself"}, status=status.HTTP_400_BAD_REQUEST)

        follow, created = Follow.objects.get_or_create(follower=request.user, following=following_user)
        if not created:
            follow.delete()
            cache.delete(f"user_followers_{following_user.id}")  # Invalidate cache on unfollow
            cache.delete(f"user_profile_{following_user.id}")  # Invalidate profile cache
            return Response({"message": "Unfollowed user"}, status=status.HTTP_200_OK)
        
        cache.delete(f"user_followers_{following_user.id}")  # Invalidate cache on follow
        cache.delete(f"user_profile_{following_user.id}")  # Invalidate profile cache
        return Response({"message": "Followed user"}, status=status.HTTP_201_CREATED)

class UserFollowersView(generics.RetrieveAPIView):
    """
    Retrieves a specific user's follower count and following count.
    Allows ordering by follower count.
    """
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering_fields = ['followers_count', 'following_count']

    def get(self, request, *args, **kwargs):
        user_id = kwargs['user_id']
        cache_key = f"user_followers_{user_id}"

        # Check if followers count is cached
        cached_data = cache.get(cache_key)
        if cached_data:
            return Response(cached_data)

        # Fetch user and follower data
        user = get_object_or_404(User, id=user_id)
        followers_count = Follow.objects.filter(following=user).count()
        following_count = Follow.objects.filter(follower=user).count()

        response_data = {
            "user": user.username,
            "followers_count": followers_count,
            "following_count": following_count,
        }

        # Cache the data for performance improvement
        cache.set(cache_key, response_data, timeout=300)  # Cache for 5 minutes

        return Response(response_data)


# -------------------- ALL USERS FOLLOWERS VIEW --------------------
class AllUsersFollowersView(generics.ListAPIView):
    """
    Endpoint to retrieve all users along with their follower count.
    Allows filtering by username and ordering by followers_count.
    Implements caching for optimized performance.
    """
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = FeedPagination  # Apply pagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['id']
    search_fields = ['username']
    ordering_fields = ['username', 'followers_count', 'following_count']

    def get_queryset(self):
        return User.objects.annotate(
            followers_count=Count('followers', distinct=True),
            following_count=Count('following', distinct=True)
        )

    def list(self, request, *args, **kwargs):
        cache_key = "all_users_followers"
        cached_data = cache.get(cache_key)

        if cached_data:
            logger.info("Cache hit: Fetching all users' followers from cache.")
            return Response(cached_data, status=status.HTTP_200_OK)

        logger.info("Cache miss: Fetching all users' followers from database.")
        queryset = self.get_queryset()
        paginated_queryset = self.paginate_queryset(queryset)

        data = [{
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "followers_count": user.followers_count,
            "following_count": user.following_count,
        } for user in paginated_queryset]

        response = self.get_paginated_response(data)

        # Cache the paginated response for 5 minutes
        cache.set(cache_key, response.data, timeout=CACHE_TIMEOUT)
        logger.info("Cache set: Cached all users' followers data.")

        return response
    
# -------------------- USER FEED --------------------
class UserFeedView(generics.ListAPIView):
    """
    Get posts from followed users, liked posts, and comments.
    Includes filtering, ordering, pagination, and caching.
    """
    serializer_class = PostSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = FeedPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['id']
    search_fields = ['title', 'content', 'author__username']
    ordering_fields = ['id', 'created_at', 'title', 'content', 'author__username']

    def get_queryset(self):
        """
        Retrieves posts from followed users, liked posts, and commented posts.
        Uses caching to optimize performance.
        """
        user = self.request.user
        page_number = self.request.query_params.get("page", 1)
        cache_key = f"user_feed_{user.id}_page_{page_number}"
        cached_feed = cache.get(cache_key)

        if cached_feed:
            logger.info(f"Cache hit: Fetching user feed page {page_number} from cache for user {user.id}.")
            return Post.objects.filter(id__in=[post["id"] for post in cached_feed]).order_by('-created_at')

        logger.info(f"Cache miss: Fetching user feed from database for user {user.id}.")
        followed_users = Follow.objects.filter(follower=user).values_list('following', flat=True)

        queryset = Post.objects.filter(
            Q(author_id__in=followed_users) | Q(likes__user=user) | Q(comments__author=user)
        ).distinct().order_by('-created_at')

        paginated_queryset = self.paginate_queryset(queryset)

        # **Store serialized data in cache but return a QuerySet**
        serialized_data = PostSerializer(paginated_queryset, many=True).data
        cache.set(cache_key, serialized_data, CACHE_TIMEOUT)
        logger.info(f"Cache set: Cached user feed page {page_number} for user {user.id}.")

        return queryset  # Return QuerySet instead of cached list

    def list(self, request, *args, **kwargs):
        """
        Ensures paginated responses are cached.
        """
        page_number = request.query_params.get("page", 1)
        cache_key = f"user_feed_{request.user.id}_page_{page_number}"
        cached_data = cache.get(cache_key)

        if cached_data:
            logger.info(f"Cache hit: Returning cached paginated response for user {request.user.id} page {page_number}.")
            return Response(cached_data, status=status.HTTP_200_OK)

        response = super().list(request, *args, **kwargs)

        # Cache the paginated response
        cache.set(cache_key, response.data, CACHE_TIMEOUT)
        logger.info(f"Cache set: Cached paginated user feed for user {request.user.id} page {page_number}.")

        return response

    def perform_create(self, serializer):
        """
        Handles new post creation and cache invalidation.
        """
        serializer.save(author=self.request.user)

        # **Manually delete user feed cache**
        self.clear_user_feed_cache()

        logger.info(f"Cache invalidated: Feed caches for user {self.request.user.id} and their followers cleared.")

    def clear_user_feed_cache(self):
        """
        **Manually deletes cached user feed pages.**
        """
        logger.info(f"Clearing cached feed pages for user {self.request.user.id}...")
        page = 1
        while True:
            cache_key = f"user_feed_{self.request.user.id}_page_{page}"
            if cache.get(cache_key):
                cache.delete(cache_key)
                logger.info(f"Cache deleted: {cache_key}")
            else:
                break  # Stop when no more pages exist
            page += 1

# -------------------- PROFILE VIEW --------------------
class UserProfileView(generics.RetrieveAPIView):
    """
    Retrieves logged-in user details, posts, and comments.
    Ensures pagination applies automatically.
    Implements caching with logging.
    """
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = FeedPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering_fields = ['title', 'content', 'created_at']

    def get_queryset(self):
        return User.objects.filter(id=self.request.user.id)

    def get(self, request, *args, **kwargs):
        cache_key = f"user_profile_{request.user.id}"
        cached_profile = cache.get(cache_key)

        if cached_profile:
            logger.info(f"Cache hit: Fetching profile for user {request.user.id}.")
            return Response(cached_profile, status=status.HTTP_200_OK)

        logger.info(f"Cache miss: Fetching profile for user {request.user.id} from database.")
        user = self.get_queryset().first()
        if not user:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        # Fetch posts and comments with pagination
        posts = Post.objects.filter(author=user).order_by('-created_at')
        paginated_posts = self.paginate_queryset(posts)

        comments = Comment.objects.filter(author=user).order_by('-created_at')
        paginated_comments = self.paginate_queryset(comments)

        response_data = {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "profile_photo": user.profile_photo if hasattr(user, 'profile_photo') else None,
            "followers_count": user.followers.count(),
            "following_count": user.following.count(),
            "posts": PostSerializer(paginated_posts, many=True).data,
            "comments": CommentSerializer(paginated_comments, many=True).data,
        }

        cache.set(cache_key, response_data, CACHE_TIMEOUT)
        logger.info(f"Cache set: Profile for user {request.user.id} cached.")

        return self.get_paginated_response(response_data)

    def perform_update(self, serializer):
        instance = self.get_object()
        serializer.save()

        # Invalidate cache on profile update
        cache.delete(f"user_profile_{instance.id}")
        logger.info(f"Cache invalidated: Profile for user {instance.id} updated.")

# -------------------- UPLOAD PHOTO VIEW --------------------
class UploadPhotoView(generics.CreateAPIView):
    """
    Allows users to upload a profile photo.
    Implements caching to avoid redundant uploads.
    Logs cache behavior for debugging.
    """
    serializer_class = UploadPhotoSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            uploaded_photo = serializer.validated_data['photo']

            # Upload photo to Google Drive
            drive_url = upload_to_google_drive(uploaded_photo, request.user.username)

            # Update user's profile photo URL
            request.user.profile_photo = drive_url
            request.user.save()

            # Invalidate and set new cache only after successful upload
            cache_key = f"profile_photo_{request.user.id}"
            cache.delete(cache_key)  # Invalidate old cache
            cache.set(cache_key, drive_url, timeout=600)  # Store new cache
            logger.info(f"Cache updated: Profile photo for user {request.user.id}.")

            return Response({
                "message": "Profile photo updated",
                "drive_url": drive_url
            }, status=status.HTTP_201_CREATED)

        logger.error(f"Photo upload failed: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)