from rest_framework import generics, permissions
from django.contrib.auth.models import User
from .models import Post, Comment
from .serializers import UserSerializer, PostSerializer, CommentSerializer
from .permissions import IsOwnerOrAdmin, IsAdminOrReadOnly
from rest_framework import serializers

class UserListCreate(generics.ListCreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAdminUser]  # Only admins can create users

class UserRetrieveUpdateDestroy(generics.RetrieveUpdateDestroyAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAdminUser]  # Only admins can update/delete users

class PostListCreate(generics.ListCreateAPIView):
    queryset = Post.objects.all()
    serializer_class = PostSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]  # Anyone can read, only authenticated users can post.

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)  # Assign the logged-in user as the post author

class PostRetrieveUpdateDestroy(generics.RetrieveUpdateDestroyAPIView):
    queryset = Post.objects.all()
    serializer_class = PostSerializer
    permission_classes = [IsOwnerOrAdmin]  # Users can edit/delete only their own posts, but admins can do everything

class CommentListCreate(generics.ListCreateAPIView):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]  # Anyone can read, only authenticated users can post.

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)  # Assign the logged-in user as the comment author

class CommentRetrieveUpdateDestroy(generics.RetrieveUpdateDestroyAPIView):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    permission_classes = [IsOwnerOrAdmin]  # Users can edit/delete only their own comments, but admins can do everything

class PostSerializer(serializers.ModelSerializer):
    author = serializers.ReadOnlyField(source='author.username')  # Prevent users from changing the author

    class Meta:
        model = Post
        fields = ['id', 'content', 'author', 'created_at', 'comments']

class CommentSerializer(serializers.ModelSerializer):
    author = serializers.ReadOnlyField(source='author.username')  # Prevent users from changing the author

    class Meta:
        model = Comment
        fields = ['id', 'text', 'author', 'post', 'created_at']