from django.db import models
from django.contrib.auth.models import User
from auditlog.registry import auditlog


class Post(models.Model):
    POST_TYPES = [
        ('text', 'Text'),
        ('image', 'Image'),
        ('video', 'Video'),
    ]
    
    PRIVACY_CHOICES = [
        ('public', 'Public'),
        ('private', 'Private'),
    ]

    title = models.CharField(max_length=255, default="Default Title")
    content = models.TextField()
    post_type = models.CharField(max_length=10, choices=POST_TYPES, default='text')
    metadata = models.JSONField(blank=True, default=dict)
    image = models.ImageField(upload_to='posts/images/', blank=True, null=True)
    video = models.FileField(upload_to='posts/videos/', blank=True, null=True)
    author = models.ForeignKey(User, related_name='posts', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    privacy = models.CharField(max_length=10, choices=PRIVACY_CHOICES, default='public')

    def like_count(self):
        return self.likes.count()

    def comment_count(self):
        return self.comments.count()

    def __str__(self):
        return f"{self.title} by {self.author.username}"

class Comment(models.Model):
    COMMENT_TYPES = [
        ('text', 'Text'),
        ('image', 'Image'),
        ('video', 'Video'),
    ]

    content = models.TextField()
    comment_type = models.CharField(max_length=10, choices=COMMENT_TYPES, default='text')
    metadata = models.JSONField(blank=True, default=dict)
    image = models.ImageField(upload_to='comments/images/', blank=True, null=True)
    video = models.FileField(upload_to='comments/videos/', blank=True, null=True)
    author = models.ForeignKey(User, related_name='comments', on_delete=models.CASCADE)
    post = models.ForeignKey(Post, related_name='comments', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def like_count(self):
        return self.likes.count()

    def __str__(self):
        return f"Comment by {self.author.username} on {self.post.title}"


class Like(models.Model):
    user = models.ForeignKey(User, related_name='likes', on_delete=models.CASCADE)
    post = models.ForeignKey(Post, related_name='likes', on_delete=models.CASCADE, null=True, blank=True)
    comment = models.ForeignKey(Comment, related_name='likes', on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'post', 'comment')  # Ensures a user can like a post or comment only once

    def __str__(self):
        if self.post:
            return f"Like by {self.user.username} on post '{self.post.title}'"
        return f"Like by {self.user.username} on comment {self.comment.id}"

class Follow(models.Model):
    follower = models.ForeignKey(User, related_name="following", on_delete=models.CASCADE)
    following = models.ForeignKey(User, related_name="followers", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('follower', 'following')  # Prevent duplicate follows

    def __str__(self):
        return f"{self.follower.username} follows {self.following.username}"

auditlog.register(Post)
auditlog.register(Comment)
auditlog.register(Like)
auditlog.register(Follow)

User.add_to_class('profile_photo', models.URLField(blank=True, null=True))

