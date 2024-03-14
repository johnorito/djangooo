from django.db import models


class Tenant(models.Model):
    id = models.AutoField(primary_key=True)


class TenantUser(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    id = models.IntegerField()

    class Meta:
        constraints = [
            models.PrimaryKeyConstraint(
                fields=("tenant_id", "id"), name="tenant_user_pk"
            ),
        ]


class TenantUserComment(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    id = models.IntegerField()
    user_id = models.IntegerField()
    user = models.ForeignObject(
        TenantUser,
        on_delete=models.CASCADE,
        from_fields=("tenant_id", "user_id"),
        to_fields=("tenant_id", "id"),
    )

    class Meta:
        constraints = [
            models.PrimaryKeyConstraint(
                fields=("tenant_id", "id"), name="tenant_user_comment_pk"
            ),
        ]
