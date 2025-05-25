# PaperDigestBot

This project is a bot for digesting papers.

## Database Initialization

To initialize the PostgreSQL database using Podman, ensure your `vchord-postgres` container is running and your `.env` file is correctly configured with `POSTGRES_USER` and `POSTGRES_DB`.

Then, run the following command from the project root directory:

```bash
podman exec -i vchord-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < db/init.sql
```

This command executes the `db/init.sql` script inside the running `vchord-postgres` container, setting up the necessary tables and schema for the application.

**Troubleshooting:**

If you encounter errors like `UndefinedColumn` (e.g., for `created_at`), it likely means the database schema was not updated correctly. To resolve this:

1. Stop your Python application and the `vchord-postgres` Podman container.
2. **Crucially, remove the old database data volume.** If you mapped a host directory (e.g., `./pg_data`), delete it: `rm -rf ./pg_data`. If it's a named Podman volume, use `podman volume rm <volume_name>`. **Warning:** This deletes all existing database data.
3. Restart the `vchord-postgres` container. This will create a fresh, empty database.
4. Re-run the `podman exec ... psql ... < db/init.sql` command above to apply the latest schema.
5. Restart your Python application.
