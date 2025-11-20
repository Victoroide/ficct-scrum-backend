# Generated manually for adding author_name index to GitHubCommit model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("integrations", "0001_initial"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="githubcommit",
            index=models.Index(fields=["author_name"], name="github_comm_author__idx"),
        ),
    ]
