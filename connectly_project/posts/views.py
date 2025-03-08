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

# ------------------- PAGE NUMBER ----------------------
class FeedPagination(PageNumberPagination):
    page_size = 2  # Number of items per page
    page_size_query_param = 'page_size'
    max_page_size = 3  # Optional: Limit max results per page

# -------------------- LOGGER --------------------------
logger = LoggerSingleton().get_logger()

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
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAdminOrReadOnly]

class UserListView(generics.ListAPIView):
    """
    Lists users with profile photo, followers count, and following count.
    Prevents non-admin users from creating new users.
    """
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

# -------------------- POST VIEWS --------------------
class PostListCreate(generics.ListCreateAPIView):
    queryset = Post.objects.all()
    serializer_class = PostSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['id']
    search_fields = ['title', 'content', 'author__username']
    ordering_fields = ['id', 'created_at', 'title', 'content']
    pagination_class = FeedPagination

    def perform_create(self, serializer):
        data = self.request.data
        try:
            post = PostFactory.create_post(
                post_type=data['post_type'],
                title=data['title'],
                content=data.get('content', ''),
                metadata=data.get('metadata', {}),
                author=self.request.user
            )
            if 'image' in self.request.FILES:
                post.image = self.request.FILES['image']
            if 'video' in self.request.FILES:
                post.video = self.request.FILES['video']

            post.save()
            serializer.instance = post
            logger.info(f"Post created: '{post.title}' by {self.request.user.username}")
        except ValueError as e:
            logger.error(f"Post creation failed: {str(e)}")
            raise serializers.ValidationError(str(e))

class PostRetrieveUpdateDestroy(generics.RetrieveUpdateDestroyAPIView):
    queryset = Post.objects.all()
    serializer_class = PostSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrAdmin]

    def perform_update(self, serializer):
        if 'author' in serializer.validated_data:
            del serializer.validated_data['author']
        instance = self.get_object()
        super().perform_update(serializer)
        logger.info(f"Post updated: '{instance.title}' by {self.request.user.username}")

    def perform_destroy(self, instance):
        logger.warning(f"Post deleted: '{instance.title}' by {self.request.user.username}")
        super().perform_destroy(instance)

# -------------------- COMMENT VIEWS --------------------
class CommentListCreate(generics.ListCreateAPIView):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['id']
    search_fields = ['content', 'author__username']
    ordering_fields = ['id', 'created_at', 'content']
    pagination_class = FeedPagination

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

            comment.save()  # Save comment with attached files
            serializer.instance = comment

            logger.info(f"Comment created on Post ID {comment.post.id} by {self.request.user.username}")

        except ValueError as e:
            logger.error(f"Comment creation failed: {str(e)}")
            raise serializers.ValidationError(str(e))

class CommentRetrieveUpdateDestroy(generics.RetrieveUpdateDestroyAPIView):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrAdmin]

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
            return Response({"message": "Unfollowed user"}, status=status.HTTP_200_OK)
        
        return Response({"message": "Followed user"}, status=status.HTTP_201_CREATED)


class UserFollowersView(generics.RetrieveAPIView):
    """
    Retrieves a specific user's follower count and following count.
    Allows ordering by follower count.
    """
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering_fields = ['followers_count']

    def get(self, request, *args, **kwargs):
        user = get_object_or_404(User, id=kwargs['user_id'])
        followers_count = Follow.objects.filter(following=user).count()
        following_count = Follow.objects.filter(follower=user).count()
        
        return Response({
            "user": user.username,
            "followers_count": followers_count,
            "following_count": following_count,
        })


class AllUsersFollowersView(generics.ListAPIView):
    """
    Endpoint to retrieve all users along with their follower count.
    Allows filtering by username and ordering by followers_count.
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
        queryset = self.get_queryset()
        data = []

        for user in queryset:
            data.append({
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "followers_count": user.followers_count,
                "following_count": user.following_count,
            })

        return Response(data, status=status.HTTP_200_OK)

    
# -------------------- USER FEED --------------------
class UserFeedView(generics.ListAPIView):
    """
    Get posts from followed users, liked posts, and comments.
    Includes filtering and ordering.
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

        # Get posts from followed users, liked posts, and commented posts
        return Post.objects.filter(
            Q(author_id__in=followed_users) | 
            Q(likes__user=user) | 
            Q(comments__author=user)
        ).distinct().order_by('-created_at').prefetch_related(
            Prefetch('comments'),
            Prefetch('likes')
        )

# -------------------- PROFILE VIEW WITH UPLOAD --------------------
class UserProfileView(generics.RetrieveAPIView):
    """
    Retrieves logged-in user details, posts, and comments.
    Ensures pagination applies automatically.
    """
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = FeedPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering_fields = ['title', 'content', 'created_at']

    def get_queryset(self):
        return User.objects.filter(id=self.request.user.id)

    def get(self, request, *args, **kwargs):
        user = self.get_queryset().first()

        if not user:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        # 🔹 Apply pagination to posts
        posts = Post.objects.filter(author=user).order_by('-created_at')
        paginated_posts = self.paginate_queryset(posts)

        # 🔹 Apply pagination to comments
        comments = Comment.objects.filter(author=user).order_by('-created_at')
        paginated_comments = self.paginate_queryset(comments)

        # 🔹 Generate paginated response
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

        return self.get_paginated_response(response_data)


class UploadPhotoView(generics.CreateAPIView):
    serializer_class = UploadPhotoSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            uploaded_photo = serializer.validated_data['photo']
            
            # Get new Google Drive URL
            drive_url = upload_to_google_drive(uploaded_photo, request.user.username)

            # Update the user's profile photo URL
            request.user.profile_photo = drive_url
            request.user.save()

            return Response({"message": "Profile photo updated", "drive_url": drive_url}, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)