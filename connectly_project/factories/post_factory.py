from posts.models import Post

class PostFactory:
    @staticmethod
    def create_post(post_type, title, content='', metadata=None, author=None):
        if post_type not in dict(Post.POST_TYPES):
            raise ValueError("Invalid post type")

        # Ensure metadata is properly handled
        if post_type == "image" and not metadata:
            raise ValueError("Metadata is required for image posts")

        if author is None:
            raise ValueError("Author is required for creating a post")

        return Post.objects.create(
            title=title,
            content=content,
            post_type=post_type,
            metadata=metadata or {},
            author=author
        )
