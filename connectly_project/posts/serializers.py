from rest_framework import serializers
from .models import Post, Comment, Like, Follow
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    profile_photo = serializers.CharField(source="profile.profile_photo", read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'is_staff', 'profile_photo']

    def create(self, validated_data):
        validated_data['password'] = make_password(validated_data['password'])
        return User.objects.create(**validated_data)

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        if password:
            instance.password = make_password(password)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
    def get_profile_photo(self, obj):
        return obj.profile.profile_photo if hasattr(obj, 'profile') else None


class CommentSerializer(serializers.ModelSerializer):
    author = serializers.ReadOnlyField(source='author.username')
    post = serializers.PrimaryKeyRelatedField(queryset=Post.objects.all())
    like_count = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = ['id', 'content', 'comment_type', 'metadata', 'image', 'video', 'author', 'post', 'created_at', 'like_count']

    def get_like_count(self, obj):
        return obj.like_count()



class PostSerializer(serializers.ModelSerializer):
    comments = CommentSerializer(many=True, read_only=True)
    author = serializers.ReadOnlyField(source='author.username')
    like_count = serializers.SerializerMethodField()
    comment_count = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = ['id', 'title', 'content', 'post_type', 'metadata', 'image', 'video',
                  'author', 'created_at', 'comments', 'like_count', 'comment_count', 'privacy']

    def get_like_count(self, obj):
        return obj.like_count()

    def get_comment_count(self, obj):
        return obj.comment_count()

class LikeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Like
        fields = ['id', 'user', 'post', 'comment', 'created_at']

class FollowSerializer(serializers.ModelSerializer):
    class Meta:
        model = Follow
        fields = ['id', 'follower', 'following', 'created_at']

class UploadPhotoSerializer(serializers.Serializer):
    photo = serializers.ImageField()

