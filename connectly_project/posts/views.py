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
    permission_classes = [permissions.IsAuthenticated]  # Only authenticated users can view posts

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)  # Assign the logged-in user as the post author

class PostRetrieveUpdateDestroy(generics.RetrieveUpdateDestroyAPIView):
    queryset = Post.objects.all()
    serializer_class = PostSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrAdmin]  # Only owners or admin can update or delete

    def perform_update(self, serializer):
        if 'author' in serializer.validated_data:
            del serializer.validated_data['author']  # Prevent users from changing the post's author field
        super().perform_update(serializer)

class CommentListCreate(generics.ListCreateAPIView):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticated]  # Only authenticated users can view comments

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)  # Assign the logged-in user as the comment author

class CommentRetrieveUpdateDestroy(generics.RetrieveUpdateDestroyAPIView):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrAdmin]  # Only owners or admin can update or delete

    def perform_update(self, serializer):
        if 'author' in serializer.validated_data:
            del serializer.validated_data['author']  # Prevent users from changing the comment's author field
        super().perform_update(serializer)