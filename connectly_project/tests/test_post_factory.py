from django.test import TestCase
from factories.post_factory import PostFactory
from posts.models import Post, User  # Fixed of the import issue

class PostFactoryTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="testuser")  # Create a user before tests

    def test_create_text_post(self):
        post = PostFactory.create_post(
            post_type="text",
            title="Test Post",
            content="This is a sample post",
            metadata={},
            author=self.user  # Ensure author is passed
        )

        self.assertEqual(post.title, "Test Post")
        self.assertEqual(post.post_type, "text")
        self.assertEqual(post.content, "This is a sample post")
        self.assertEqual(post.author, self.user)

    def test_create_invalid_post(self):
        with self.assertRaises(ValueError):
            PostFactory.create_post(
                post_type="invalid",
                title="Invalid Post",
                author=self.user
            )

    def test_create_image_post_without_metadata(self):
        with self.assertRaises(ValueError):
            PostFactory.create_post(
                post_type="image",
                title="Image Post",
                author=self.user
            )
