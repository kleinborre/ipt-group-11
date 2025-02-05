from rest_framework import serializers
from .models import Post, Comment
from django.contrib.auth.models import User
import bcrypt
from argon2 import PasswordHasher
# from django.contrib.auth.hashers import make_password  # This import is optional, we'll use argon2 instead

class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'is_staff']

    def create(self, validated_data):
        password = validated_data.pop('password')
        salt = bcrypt.gensalt()
        salted_password = bcrypt.hashpw(password.encode(), salt)
        ph = PasswordHasher()
        hashed_password = ph.hash(salted_password.decode())
        user = User.objects.create(**validated_data)
        user.password = hashed_password
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)  # Check if password is provided for update
        if password:
            # Salt with bcrypt
            salt = bcrypt.gensalt()
            salted_password = bcrypt.hashpw(password.encode('utf-8'), salt)
            
            # Hash with Argon2
            ph = PasswordHasher()
            hashed_password = ph.hash(salted_password.decode('utf-8'))
            
            instance.password = hashed_password
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance

class PostSerializer(serializers.ModelSerializer):
    comments = serializers.StringRelatedField(many=True, read_only=True)

    class Meta:
        model = Post
        fields = ['id', 'content', 'author', 'created_at', 'comments']

class CommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = ['id', 'text', 'author', 'post', 'created_at']

    def validate_post(self, value):
        if not Post.objects.filter(id=value.id).exists():
            raise serializers.ValidationError("Post not found.")
        return value

    def validate_author(self, value):
        if not User.objects.filter(id=value.id).exists():
            raise serializers.ValidationError("Author not found.")
        return value
