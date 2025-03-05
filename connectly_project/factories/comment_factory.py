from posts.models import Comment

class CommentFactory:
    @staticmethod
    def create_comment(comment_type, content='', metadata=None, author=None, post=None):
        if comment_type not in dict(Comment.COMMENT_TYPES):
            raise ValueError("Invalid comment type")

        if comment_type == "image" and not metadata:
            raise ValueError("Metadata is required for image comments")
        if comment_type == "video" and not metadata:
            raise ValueError("Metadata is required for video comments")
        if not author or not post:
            raise ValueError("Author and Post are required")

        return Comment.objects.create(
            content=content,
            comment_type=comment_type,
            metadata=metadata or {},
            author=author,
            post=post
        )