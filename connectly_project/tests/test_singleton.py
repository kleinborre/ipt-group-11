from django.test import TestCase
from singletons.config_manager import ConfigManager  

class ConfigManagerTest(TestCase):
    def test_singleton_instance(self):
        config1 = ConfigManager()
        config2 = ConfigManager()

        # Assert that both instances are the same (singleton behavior)
        self.assertIs(config1, config2)

    def test_settings_persistence(self):
        config = ConfigManager()
        config.set_setting("DEFAULT_PAGE_SIZE", 50)

        # Assert that setting persists across instances
        new_config = ConfigManager()
        self.assertEqual(new_config.get_setting("DEFAULT_PAGE_SIZE"), 50)