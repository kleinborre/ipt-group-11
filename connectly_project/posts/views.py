from rest_framework import generics, permissions, status, serializers
from rest_framework.response import Response
from django.contrib.auth.models import User
from .models import Post, Comment, Like, Follow
from .serializers import UserSerializer, PostSerializer, CommentSerializer, LikeSerializer, FollowSerializer
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

# ------------------- PAGE NUMBER ----------------------
class FeedPagination(PageNumberPagination):
    page_size = 2  # Number of items per page
    # page_size_query_param = 'page_size'
    max_page_size = 3  # Optional: Limit max results per page

# -------------------- LOGGER --------------------------
logger = LoggerSingleton().get_logger()

# ------------------- USER VIEWS -----------------------
class UserListCreate(generics.ListCreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['id']
    search_fields = ['username', 'email']
    ordering_fields = ['id', 'username', 'email']
    pagination_class = FeedPagination  # Apply pagination


class UserRetrieveUpdateDestroy(generics.RetrieveUpdateDestroyAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAdminOrReadOnly]

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

        # Get or create user
        user_model = get_user_model()
        user, _ = user_model.objects.get_or_create(email=email, defaults={"username": email.split("@")[0]})

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
        followers_count = user.followers.count()
        following_count = user.following.count()
        
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
            followers_count=Count('followers'),
            following_count=Count('following')
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

# -------------------- USER PROFILE VIEW --------------------
class UserProfileView(generics.ListAPIView):
    """
    Get the logged-in user's profile with their posts and comments.
    Includes filtering, searching, ordering, and pagination.
    """
    serializer_class = PostSerializer  # Default to posts; switch based on request
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = FeedPagination  # Apply pagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['id']
    search_fields = ['title', 'content', 'author__username']
    ordering_fields = ['id', 'created_at', 'title', 'content']

    def get_queryset(self):
        user = self.request.user
        content_type = self.request.GET.get("content", "posts")  # Default to posts

        if content_type == "comments":
            return Comment.objects.filter(author=user).order_by('-created_at')
        return Post.objects.filter(author=user).order_by('-created_at')