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
    queryset = Post.objects.select_related('author') \
        .prefetch_related('comments__author', 'likes__user') \
        .order_by('-created_at')
    serializer_class = PostSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = FeedPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['id']
    search_fields = ['title', 'content', 'author__username']
    ordering_fields = ['id', 'created_at', 'title', 'content']

    def get_queryset(self):
        """
        Only show public posts OR private posts authored by current user.
        """
        user = self.request.user
        return Post.objects.filter(
            Q(privacy='public') | Q(author=user)
        ).order_by('-created_at')

    def list(self, request, *args, **kwargs):
        """
        Caches paginated post list per user per page.
        """
        user_id = request.user.id
        page_number = request.query_params.get("page", 1)
        cache_key = f"posts_list_user_{user_id}_page_{page_number}"
        cached_data = cache.get(cache_key)

        if cached_data:
            logger.info(f"Cache hit: Returning cached posts for user {user_id} page {page_number}.")
            return Response(cached_data, status=status.HTTP_200_OK)

        logger.info(f"Cache miss: Fetching posts for user {user_id} page {page_number}.")
        response = super().list(request, *args, **kwargs)
        cache.set(cache_key, response.data, CACHE_TIMEOUT)
        logger.info(f"Cache set: posts_list_user_{user_id}_page_{page_number}")
        return response

    def perform_create(self, serializer):
        """
        Creates a new post and clears cached lists.
        """
        data = self.request.data
        try:
            post = PostFactory.create_post(
                post_type=data['post_type'],
                title=data['title'],
                content=data.get('content', ''),
                metadata=data.get('metadata', {}),
                author=self.request.user,
                privacy=data.get('privacy', 'public')
            )

            if 'image' in self.request.FILES:
                post.image = self.request.FILES['image']
            if 'video' in self.request.FILES:
                post.video = self.request.FILES['video']

            post.save()
            serializer.instance = post

            self.clear_all_post_page_caches()

            # Also clear feed caches for all users
            UserFeedView().clear_all_feed_page_caches()
            
            logger.info(f"Post created: '{post.title}' by {self.request.user.username}")

        except ValueError as e:
            logger.error(f"Post creation failed: {str(e)}")
            raise serializers.ValidationError(str(e))

    def clear_all_post_page_caches(self):
        """
        Clear cached post pages for all users (across all page numbers).
        """
        logger.info("Clearing cached post list pages for all users...")
        for user in User.objects.all():
            user_id = user.id
            page = 1
            while True:
                cache_key = f"posts_list_user_{user_id}_page_{page}"
                if cache.get(cache_key):
                    cache.delete(cache_key)
                    logger.info(f"Cache deleted: {cache_key}")
                else:
                    break
                page += 1

class PostRetrieveUpdateDestroy(generics.RetrieveUpdateDestroyAPIView):
    queryset = Post.objects.all()
    serializer_class = PostSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrAdmin]

    def get_object(self):
        post_id = self.kwargs["pk"]
        post = get_object_or_404(Post, id=post_id)

        # Restrict view of private posts from others, including admin
        if post.privacy == 'private' and post.author != self.request.user:
            if self.request.method == 'GET':
                raise serializers.ValidationError("You are not authorized to view this private post.")

        self.check_object_permissions(self.request, post)
        return post

    def perform_update(self, serializer):
        instance = self.get_object()
        serializer.save()

        # Invalidate detail and list caches
        cache.delete(f"post_{instance.id}")
        self.clear_all_post_page_caches()

        # Also clear feed caches for all users
        UserFeedView().clear_all_feed_page_caches()

        logger.info(f"Cache invalidated: Post {instance.id} updated.")

    def perform_destroy(self, instance):
        post_id = instance.id
        instance.delete()

        # Invalidate detail and list caches
        cache.delete(f"post_{post_id}")
        self.clear_all_post_page_caches()

        # Also clear feed caches for all users
        UserFeedView().clear_all_feed_page_caches()

        logger.info(f"Cache invalidated: Post {post_id} deleted.")

    def clear_all_post_page_caches(self):
        logger.info("Clearing cached post list pages for all users...")
        for user in User.objects.all():
            user_id = user.id
            page = 1
            while True:
                cache_key = f"posts_list_user_{user_id}_page_{page}"
                if cache.get(cache_key):
                    cache.delete(cache_key)
                    logger.info(f"Cache deleted: {cache_key}")
                else:
                    break
                page += 1

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

            if 'image' in files:
                comment.image = files['image']
            if 'video' in files:
                comment.video = files['video']

            comment.save()
            serializer.instance = comment

            cache.delete("comments_list")
            self.clear_related_post_cache(comment.post.id)

            logger.info(f"Comment created on Post ID {comment.post.id} by {self.request.user.username}")
            logger.info(f"Cache invalidated: Related post caches cleared for Post ID {comment.post.id}.")

        except ValueError as e:
            logger.error(f"Comment creation failed: {str(e)}")
            raise serializers.ValidationError(str(e))

    def clear_related_post_cache(self, post_id):
        """
        Clears individual post detail cache and paginated post list caches.
        """
        # Clear specific post detail view
        post_cache_key = f"post_{post_id}"
        cache.delete(post_cache_key)
        logger.info(f"Cache deleted: {post_cache_key}")

        # Clear paginated list view caches
        page = 1
        while True:
            list_cache_key = f"posts_list_page_{page}"
            if cache.get(list_cache_key):
                cache.delete(list_cache_key)
                logger.info(f"Cache deleted: {list_cache_key}")
            else:
                break
            page += 1

        
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
        return get_object_or_404(Comment, id=comment_id)

    def perform_update(self, serializer):
        instance = self.get_object()
        serializer.save()
        cache.delete(f"comment_{instance.id}")
        cache.delete("comments_list")
        self.clear_related_post_cache(instance.post.id)
        logger.info(f"Comment {instance.id} updated. Cache invalidated.")

    def perform_destroy(self, instance):
        post_id = instance.post.id
        instance.delete()

        cache.delete(f"comment_{instance.id}")
        cache.delete("comments_list")
        logger.info(f"Comment {instance.id} deleted. Cache invalidated.")

        self.clear_related_post_cache(post_id)

    def clear_related_post_cache(self, post_id):
        """
        Clears post detail cache and all paginated post list caches.
        """
        logger.info(f"[Comment] Clearing cached post detail and list for post {post_id}...")

        # Always delete the post detail cache
        cache.delete(f"post_{post_id}")
        logger.info(f"Cache deleted: post_{post_id}")

        # Always delete all paginated post list pages (safer and cleaner)
        page = 1
        while True:
            list_cache_key = f"posts_list_page_{page}"
            if cache.get(list_cache_key):
                cache.delete(list_cache_key)
                logger.info(f"Cache deleted: {list_cache_key}")
            else:
                break
            page += 1

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
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "id"  # Still referencing by ID

    def get_object(self):
        post = get_object_or_404(
            Post,
            author_id=self.kwargs["user_id"],
            id=self.kwargs["post_id"]
        )

        # Privacy check: only the author can view private posts
        if post.privacy == 'private' and self.request.user != post.author:
            raise serializers.ValidationError("You are not authorized to view this private post.")

        return post

class UserPostList(generics.ListAPIView):
    serializer_class = PostSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user_id = self.kwargs['user_id']
        requesting_user = self.request.user

        if requesting_user.id == int(user_id):
            # Show all posts if the user is viewing their own posts
            return Post.objects.filter(author_id=user_id)
        else:
            # Show only public posts if viewing someone else's posts
            return Post.objects.filter(author_id=user_id, privacy='public')

# -------------------- LIKE VIEWS --------------------
class LikePostView(generics.CreateAPIView):
    serializer_class = LikeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        post_id = kwargs.get("pk")
        post = get_object_or_404(Post, id=post_id)
        like, created = Like.objects.get_or_create(user=request.user, post=post)

        # Invalidate cache for individual post
        cache.delete(f"post_{post_id}")
        # Invalidate all paginated post list caches
        page = 1
        while True:
            cache_key = f"posts_list_page_{page}"
            if cache.get(cache_key):
                cache.delete(cache_key)
                logger.info(f"Cache invalidated: {cache_key}")
            else:
                break
            page += 1

        if not created:
            like.delete()
            return Response({"message": "Like removed"}, status=status.HTTP_200_OK)
        
        return Response({"message": "Post liked"}, status=status.HTTP_201_CREATED)
    
class LikeCommentView(generics.CreateAPIView):
    serializer_class = LikeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        comment = get_object_or_404(Comment, id=kwargs.get("pk"))
        post_id = comment.post.id  # Get related post ID

        like, created = Like.objects.get_or_create(user=request.user, comment=comment)
        message = "Comment liked" if created else "Like removed"
        
        if not created:
            like.delete()

        # Invalidate related post caches (for list + detail view)
        self.clear_related_post_cache(post_id)

        return Response({"message": message}, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    def clear_related_post_cache(self, post_id):
        """
        Clears the cache for the post detail and all post list pages.
        """
        logger.info(f"[LikeComment] Clearing cache for post ID {post_id}...")

        # Clear the post detail cache
        cache.delete(f"post_{post_id}")
        logger.info(f"Cache deleted: post_{post_id}")

        # Clear all post list pages (to reflect like_count on comments)
        page = 1
        while True:
            cache_key = f"posts_list_page_{page}"
            if cache.get(cache_key):
                cache.delete(cache_key)
                logger.info(f"Cache deleted: {cache_key}")
            else:
                break
            page += 1
    

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

    def clear_feed_cache_for_user(self, user_id):
        page = 1
        while True:
            cache_key = f"user_feed_page_{user_id}_{page}"
            if cache.get(cache_key):
                cache.delete(cache_key)
                logger.info(f"Cleared feed cache: {cache_key}")
            else:
                break
            page += 1

    def post(self, request, *args, **kwargs):
        following_user = get_object_or_404(User, id=kwargs['user_id'])
        if request.user == following_user:
            return Response({"error": "You cannot follow yourself"}, status=status.HTTP_400_BAD_REQUEST)

        follow, created = Follow.objects.get_or_create(follower=request.user, following=following_user)

        if not created:
            follow.delete()
            message = "Unfollowed user"
            response_status = status.HTTP_200_OK
        else:
            message = "Followed user"
            response_status = status.HTTP_201_CREATED

        cache.delete(f"user_followers_{following_user.id}")
        cache.delete(f"user_profile_{following_user.id}")
        cache.delete("all_users_followers")
        logger.info("Cache invalidated: 'all_users_followers' after follow/unfollow.")

        self.clear_feed_cache_for_user(request.user.id)

        return Response({"message": message}, status=response_status)

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
    Shows the feed with DRF pagination and per-page caching:
      - Public posts from followed users
      - Public posts the user has liked or commented on
      - The user’s own private posts
    Cache is keyed by user + page to preserve pagination navigation.
    """
    serializer_class = PostSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = FeedPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['id']
    search_fields = ['title', 'content', 'author__username']
    ordering_fields = ['id', 'created_at', 'title', 'content', 'author__username']

    def get_queryset(self):
        user = self.request.user
        followed_users = Follow.objects.filter(follower=user).values_list('following', flat=True)

        # Only show:
        #  - public posts by followed users
        #  - public posts liked by or commented on by the user
        #  - the user's own posts (including private)
        return (
            Post.objects.filter(
                Q(author__in=followed_users, privacy='public') |
                Q(likes__user=user, privacy='public') |
                Q(comments__author=user, privacy='public') |
                Q(author=user)  # includes user's private
            )
            .distinct()
            .order_by('-created_at')
        )

    def list(self, request, *args, **kwargs):
        user_id = request.user.id
        page_number = request.query_params.get("page", 1)
        cache_key = f"user_feed_page_{user_id}_{page_number}"

        cached_data = cache.get(cache_key)
        if cached_data is not None:
            logger.info(f"[UserFeedView] Cache hit for user={user_id}, page={page_number}")
            return Response(cached_data, status=status.HTTP_200_OK)

        logger.info(f"[UserFeedView] Cache miss for user={user_id}, page={page_number}")
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            paginated_response = self.get_paginated_response(serializer.data)
            cache.set(cache_key, paginated_response.data, CACHE_TIMEOUT)
            return paginated_response

        # If not enough posts to paginate, just cache minimal
        serializer = self.get_serializer(queryset, many=True)
        minimal_data = serializer.data
        cache.set(cache_key, minimal_data, CACHE_TIMEOUT)
        return Response(minimal_data, status=status.HTTP_200_OK)

    def clear_all_feed_page_caches(self):
        """
        Call this to invalidate ALL feed caches for ALL users and pages.
        Example usage in Post creation/update/deletion:
            UserFeedView().clear_all_feed_page_caches()
        """
        logger.info("[UserFeedView] Clearing ALL feed page caches for every user.")
        for user in User.objects.all():
            user_id = user.id
            page = 1
            while True:
                cache_key = f"user_feed_page_{user_id}_{page}"
                if cache.get(cache_key):
                    cache.delete(cache_key)
                    logger.info(f"Cleared feed cache: {cache_key}")
                else:
                    break
                page += 1

# -------------------- PROFILE VIEW --------------------
class UserProfileView(generics.RetrieveAPIView):
    """
    Retrieves the logged-in user's details.
    - Paginates only the user's posts
    - Comments are included without pagination
    - No caching so that it always reflects real-time changes
    """
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]  # <--- Enforce authentication
    pagination_class = None  # or your custom pagination if you want paginated posts
                             # but typically you only paginate the posts portion

    def get_queryset(self):
        # Always use the actual User model, not request.user.__class__
        User = get_user_model()
        return User.objects.filter(id=self.request.user.id)

    def get(self, request, *args, **kwargs):
        logger.info(f"Fetching profile for user {request.user.id} with pagination (if enabled).")
        
        # 1. Get the user object
        user_qs = self.get_queryset()
        if not user_qs.exists():
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
        
        user = user_qs.first()

        # 2. (Optional) Paginate the user's posts if you want
        posts_qs = Post.objects.filter(author=user).order_by('-created_at')
        # If you do want pagination on the posts, do something like:
        page = self.paginate_queryset(posts_qs)
        if page is not None:
            serialized_posts = PostSerializer(page, many=True).data
        else:
            serialized_posts = PostSerializer(posts_qs, many=True).data

        # 3. Get user comments (unpaginated or paginated—your choice)
        comments_qs = Comment.objects.filter(author=user).order_by('-created_at')
        serialized_comments = CommentSerializer(comments_qs, many=True).data

        # 4. Construct the final profile data
        profile_data = {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "profile_photo": getattr(user, 'profile_photo', None),
            "followers_count": user.followers.count(),
            "following_count": user.following.count(),
            "posts": serialized_posts,       # possibly paginated
            "comments": serialized_comments  # unpaginated
        }

        # 5. If pagination is on for posts, DRF will create pagination links for the "posts" portion
        #    and you can embed them in the final response. Or you can just return the default DRF
        #    paginated response, but that typically expects a single "results" list.
        if page is not None:
            # If you want a single unified response with the pagination metadata, do:
            return self.get_paginated_response(profile_data)
        else:
            # If no pagination was applied, just return the data
            return Response(profile_data, status=status.HTTP_200_OK)

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