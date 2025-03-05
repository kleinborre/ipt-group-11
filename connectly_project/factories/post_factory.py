from posts.models import Post

class PostFactory:
    @staticmethod
    def create_post(post_type, title, content='', metadata=None, author=None, image=None, video=None):
        if post_type not in dict(Post.POST_TYPES):
            raise ValueError("Invalid post type")

        if post_type == "image" and not metadata:
            raise ValueError("Metadata is required for image posts")
        if post_type == "video" and not metadata:
            raise ValueError("Metadata is required for video posts")
        if not author:
            raise ValueError("Author is required for creating a post")

        post = Post.objects.create(
            title=title,
            content=content,
            post_type=post_type,
            metadata=metadata or {},
            author=author
        )

        if image:
            post.image = image
        if video:
            post.video = video

        post.save()
        return post
