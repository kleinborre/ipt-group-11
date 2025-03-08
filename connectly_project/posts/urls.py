from django.urls import path
from .views import (
    UserListView, UserCreateView, UserRetrieveUpdateDestroy,
    PostListCreate, PostRetrieveUpdateDestroy, LikePostView,
    CommentListCreate, CommentRetrieveUpdateDestroy, LikeCommentView,
    UserPostCommentsList, UserPostCommentDetail, UserAllCommentsList,
    PostAllCommentsList, PostCommentDetail, AllCommentsList,
    UserPostList, UserSpecificPost, FollowUserView, UserFollowersView, AllUsersFollowersView
)

urlpatterns = [
    # -------------------- USER ENDPOINTS --------------------
    path('users/', UserListView.as_view(), name='user-list'),  # ✅ View-Only for Authenticated Users
    path('users/create/', UserCreateView.as_view(), name='user-create'),  # ✅ Admin-Only for Creating Users
    path('users/<int:pk>/', UserRetrieveUpdateDestroy.as_view(), name='user-retrieve-update-destroy'),

    # -------------------- POST ENDPOINTS --------------------
    path('', PostListCreate.as_view(), name='post-list-create'),
    path('<int:pk>/', PostRetrieveUpdateDestroy.as_view(), name='post-retrieve-update-destroy'),
    path('<int:pk>/like/', LikePostView.as_view(), name='post-like'),

    # -------------------- COMMENT ENDPOINTS --------------------
    path('comments/', CommentListCreate.as_view(), name='comment-list-create'),
    path('comments/<int:pk>/', CommentRetrieveUpdateDestroy.as_view(), name='comment-retrieve-update-destroy'),
    path('comments/<int:pk>/like/', LikeCommentView.as_view(), name='comment-like'),

    # -------------------- COMMENT TRACKING ENDPOINTS --------------------
    path('<int:post_id>/comment/<int:comment_id>/', PostCommentDetail.as_view(), name='post-comment-detail'),
    path('<int:post_id>/comments/', PostAllCommentsList.as_view(), name='post-comments-list'),
    path('comments/', AllCommentsList.as_view(), name='all-comments-list'),

    # -------------------- USER COMMENT TRACKING --------------------
    path('<int:post_id>/users/<int:user_id>/comments/<int:comment_id>/', UserPostCommentDetail.as_view(), name='user-post-comment-detail'),
    path('<int:post_id>/users/<int:user_id>/comments/', UserPostCommentsList.as_view(), name='user-post-comments-list'),
    path('users/<int:user_id>/comments/', UserAllCommentsList.as_view(), name='user-all-comments-list'),

    # -------------------- USER POST TRACKING --------------------
    path('<int:post_id>/users/<int:user_id>/', UserSpecificPost.as_view(), name='user-specific-post'),
    path('users/<int:user_id>/posts/', UserPostList.as_view(), name='user-post-list'),

    # -------------------- FOLLOW USER ENDPOINTS --------------------
    path('users/<int:user_id>/follow/', FollowUserView.as_view(), name='follow-user'),
    path('users/<int:user_id>/followers/', UserFollowersView.as_view(), name='user-followers'),
    path('users/followers/', AllUsersFollowersView.as_view(), name='all-users-followers'),
]
