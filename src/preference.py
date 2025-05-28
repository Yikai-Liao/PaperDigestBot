"""
User preference management system
Handles paper preference tracking, GitHub repository sync, and CSV management using DuckDB
"""

import csv
import io
import traceback
from datetime import datetime, timedelta
from typing import Any

import duckdb
import requests
from loguru import logger
from pydantic import BaseModel

from src.config import get_config
from src.db import db
from src.models.reaction_record import ReactionRecord
from src.models.user_setting import UserSetting
from src.pat import decrypt_pat


class PreferenceRecord(BaseModel):
    """Individual preference record data structure"""

    id: str
    preference: str

    def __init__(self, id: str, preference: str, **kwargs):
        super().__init__(id=id, preference=preference, **kwargs)


class PreferenceManager:
    """
    Manages user paper preferences and GitHub repository synchronization
    """

    def __init__(self) -> None:
        self.config = get_config()
        self._create_emoji_to_preference_map()

    def _create_emoji_to_preference_map(self) -> None:
        """Create reverse mapping from emoji to preference type"""
        self.emoji_to_preference = {}
        for preference, emojis in self.config.telegram.reaction_mapping.items():
            for emoji in emojis:
                self.emoji_to_preference[emoji] = preference

    def classify_reaction(self, emoji: str) -> str:
        """
        Classify a reaction emoji to preference type

        Args:
            emoji: The reaction emoji

        Returns:
            Preference type ('like', 'dislike', 'neutral', 'unknown')
        """
        return self.emoji_to_preference.get(emoji, "unknown")

    def get_github_reactions(self, user_id: str, days_back: int = 2) -> list[dict[str, Any]]:
        """
        Fetch reaction records from GitHub repository for the last N days

        Args:
            user_id: Telegram user ID
            days_back: Number of days to look back for reactions

        Returns:
            List of reaction dictionaries with paper_id and emoji
        """
        user_setting = UserSetting.get_by_id(user_id)
        if not user_setting:
            logger.warning(f"No user setting found for user {user_id}")
            return []

        repo_url = user_setting.repo_url
        if not repo_url:
            logger.warning(f"No repository URL found for user {user_id}")
            return []

        try:
            # Extract owner and repo from URL
            if "github.com/" in repo_url:
                parts = repo_url.replace("https://github.com/", "").split("/")
                if len(parts) >= 2:
                    owner, repo = parts[0], parts[1]
                else:
                    logger.error(f"Invalid repository URL format: {repo_url}")
                    return []
            else:
                logger.error(f"Invalid repository URL: {repo_url}")
                return []

            # Decrypt PAT
            encrypted_pat = user_setting.github_pat
            if not encrypted_pat:
                logger.warning(f"No GitHub PAT found for user {user_id}")
                return []

            try:
                decrypted_pat = decrypt_pat(encrypted_pat)
            except Exception as e:
                logger.error(f"Failed to decrypt PAT for user {user_id}: {e}")
                return []

            # Calculate date threshold
            since_date = (datetime.utcnow() - timedelta(days=days_back)).isoformat() + "Z"

            # Fetch repository data to get reactions
            headers = {
                "Authorization": f"token {decrypted_pat}",
                "Accept": "application/vnd.github.v3+json",
            }

            # Get repository contents from preference path
            preference_url = f"https://api.github.com/repos/{owner}/{repo}/contents/preference"

            response = requests.get(preference_url, headers=headers, timeout=30)
            if response.status_code == 404:
                logger.info(f"No preference folder found in repository {owner}/{repo}")
                return []
            elif response.status_code != 200:
                logger.error(f"Failed to fetch preference folder: {response.status_code}")
                return []

            # Get recent reaction records from database that match the time window
            reactions = []
            with db.session() as session:
                from sqlalchemy import and_

                recent_records = (
                    session.query(ReactionRecord)
                    .filter(
                        and_(
                            ReactionRecord.user_id == user_id,
                            ReactionRecord.created_at
                            >= (datetime.utcnow() - timedelta(days=days_back)),
                        )
                    )
                    .all()
                )

            for record in recent_records:
                reactions.append(
                    {
                        "paper_id": record.arxiv_id,
                        "emoji": record.emoji,
                        "timestamp": record.created_at.isoformat(),
                    }
                )

            logger.info(f"Found {len(reactions)} recent reactions for user {user_id}")
            return reactions

        except Exception as e:
            logger.error(f"Error fetching GitHub reactions for user {user_id}: {e}")
            logger.error(traceback.format_exc())
            return []

    def update_preference_csv(
        self, user_id: str, reactions: list[dict[str, Any]], month: str | None = None
    ) -> bool:
        """
        Update preference CSV file in GitHub repository using DuckDB for deduplication

        Args:
            user_id: Telegram user ID
            reactions: List of reaction dictionaries
            month: Target month in YYYY-MM format, defaults to current month

        Returns:
            True if update successful, False otherwise
        """
        if not reactions:
            logger.info("No reactions to update")
            return True

        user_setting = UserSetting.get_by_id(user_id)
        if not user_setting:
            logger.error(f"No user setting found for user {user_id}")
            return False

        # Default to current month
        if month is None:
            month = datetime.utcnow().strftime("%Y-%m")

        try:
            # Convert reactions to preference records
            new_records = []
            for reaction in reactions:
                preference_type = self.classify_reaction(reaction["emoji"])
                if preference_type != "unknown":  # Skip unknown emojis
                    new_records.append(
                        PreferenceRecord(id=reaction["paper_id"], preference=preference_type)
                    )

            if not new_records:
                logger.info("No valid preference records to update")
                return True

            # Use DuckDB for deduplication and merging
            return self._merge_with_duckdb(user_setting, new_records, month)

        except Exception as e:
            logger.error(f"Error updating preference CSV for user {user_id}: {e}")
            logger.error(traceback.format_exc())
            return False

    def _merge_with_duckdb(
        self, user_setting: UserSetting, new_records: list[PreferenceRecord], month: str
    ) -> bool:
        """
        Merge new preference records with existing CSV using DuckDB for deduplication

        Args:
            user_setting: User configuration
            new_records: New preference records to merge
            month: Target month in YYYY-MM format

        Returns:
            True if merge successful, False otherwise
        """
        try:
            # Create DuckDB connection
            conn = duckdb.connect(":memory:")

            # Download existing CSV if it exists
            existing_csv_content = self._download_csv_from_github(user_setting, month)

            # Create table from existing data
            if existing_csv_content:
                # Create table from existing CSV
                conn.execute(
                    """
                    CREATE TABLE existing_preferences (
                        id VARCHAR,
                        preference VARCHAR
                    )
                """
                )

                # Insert existing data
                csv_reader = csv.DictReader(io.StringIO(existing_csv_content))
                for row in csv_reader:
                    conn.execute(
                        "INSERT INTO existing_preferences VALUES (?, ?)",
                        [row["id"], row["preference"]],
                    )
            else:
                # Create empty table
                conn.execute(
                    """
                    CREATE TABLE existing_preferences (
                        id VARCHAR,
                        preference VARCHAR
                    )
                """
                )

            # Create table for new records
            conn.execute(
                """
                CREATE TABLE new_preferences (
                    id VARCHAR,
                    preference VARCHAR
                )
            """
            )

            # Insert new records
            for record in new_records:
                conn.execute(
                    "INSERT INTO new_preferences VALUES (?, ?)", [record.id, record.preference]
                )

            # Merge data with deduplication (new records override existing ones)
            merged_result = conn.execute(
                """
                WITH combined AS (
                    SELECT id, preference FROM new_preferences
                    UNION
                    SELECT e.id, e.preference 
                    FROM existing_preferences e
                    WHERE e.id NOT IN (SELECT id FROM new_preferences)
                )
                SELECT id, preference FROM combined
                ORDER BY id
            """
            ).fetchall()

            # Convert to CSV
            csv_content = self._records_to_csv(merged_result)

            # Upload to GitHub
            return self._upload_csv_to_github(user_setting, csv_content, month)

        except Exception as e:
            logger.error(f"Error merging preferences with DuckDB: {e}")
            logger.error(traceback.format_exc())
            return False
        finally:
            try:
                conn.close()
            except:
                pass

    def _download_csv_from_github(self, user_setting: UserSetting, month: str) -> str | None:
        """
        Download existing preference CSV from GitHub repository

        Args:
            user_setting: User configuration
            month: Target month in YYYY-MM format

        Returns:
            CSV content as string, or None if not found
        """
        try:
            repo_url = user_setting.repo_url
            if not repo_url or "github.com/" not in repo_url:
                return None

            parts = repo_url.replace("https://github.com/", "").split("/")
            if len(parts) < 2:
                return None

            owner, repo = parts[0], parts[1]

            # Decrypt PAT
            try:
                decrypted_pat = decrypt_pat(user_setting.github_pat)
            except Exception as e:
                logger.error(f"Failed to decrypt PAT: {e}")
                return None

            headers = {
                "Authorization": f"token {decrypted_pat}",
                "Accept": "application/vnd.github.v3+json",
            }

            # Download CSV file
            csv_url = f"https://api.github.com/repos/{owner}/{repo}/contents/preference/{month}.csv"
            response = requests.get(csv_url, headers=headers, timeout=30)

            if response.status_code == 404:
                logger.info(f"CSV file for {month} not found, will create new one")
                return None
            elif response.status_code != 200:
                logger.error(f"Failed to download CSV: {response.status_code}")
                return None

            # Decode base64 content
            import base64

            file_data = response.json()
            content = base64.b64decode(file_data["content"]).decode("utf-8")

            return content

        except Exception as e:
            logger.error(f"Error downloading CSV from GitHub: {e}")
            return None

    def _upload_csv_to_github(
        self, user_setting: UserSetting, csv_content: str, month: str
    ) -> bool:
        """
        Upload preference CSV to GitHub repository

        Args:
            user_setting: User configuration
            csv_content: CSV content to upload
            month: Target month in YYYY-MM format

        Returns:
            True if upload successful, False otherwise
        """
        try:
            repo_url = user_setting.repo_url
            if not repo_url or "github.com/" not in repo_url:
                return False

            parts = repo_url.replace("https://github.com/", "").split("/")
            if len(parts) < 2:
                return False

            owner, repo = parts[0], parts[1]

            # Decrypt PAT
            try:
                decrypted_pat = decrypt_pat(user_setting.github_pat)
            except Exception as e:
                logger.error(f"Failed to decrypt PAT: {e}")
                return False

            headers = {
                "Authorization": f"token {decrypted_pat}",
                "Accept": "application/vnd.github.v3+json",
            }

            # Check if file exists to get SHA
            csv_url = f"https://api.github.com/repos/{owner}/{repo}/contents/preference/{month}.csv"
            response = requests.get(csv_url, headers=headers, timeout=30)

            sha = None
            if response.status_code == 200:
                sha = response.json().get("sha")

            # Encode content to base64
            import base64

            encoded_content = base64.b64encode(csv_content.encode("utf-8")).decode("utf-8")

            # Prepare upload payload
            payload = {
                "message": f"Update preference data for {month}",
                "content": encoded_content,
            }

            if sha:
                payload["sha"] = sha

            # Upload file
            response = requests.put(csv_url, json=payload, headers=headers, timeout=30)

            if response.status_code in [200, 201]:
                logger.info(f"Successfully uploaded preference CSV for {month}")
                return True
            else:
                logger.error(f"Failed to upload CSV: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            logger.error(f"Error uploading CSV to GitHub: {e}")
            return False

    def _records_to_csv(self, records: list[tuple[str, str]]) -> str:
        """
        Convert database records to CSV format

        Args:
            records: List of (id, preference) tuples

        Returns:
            CSV content as string
        """
        output = io.StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow(["id", "preference"])

        # Write data
        for record in records:
            writer.writerow(record)

        return output.getvalue()

    def sync_user_preferences(self, user_id: str, days_back: int = 2) -> bool:
        """
        Synchronize user preferences from recent reactions to GitHub repository

        Args:
            user_id: Telegram user ID
            days_back: Number of days to look back for reactions

        Returns:
            True if sync successful, False otherwise
        """
        try:
            logger.info(f"Starting preference sync for user {user_id}")

            # Get recent reactions
            reactions = self.get_github_reactions(user_id, days_back)
            if not reactions:
                logger.info(f"No recent reactions found for user {user_id}")
                return True

            # Update current month's CSV
            current_month = datetime.utcnow().strftime("%Y-%m")
            success = self.update_preference_csv(user_id, reactions, current_month)

            if success:
                logger.info(f"Successfully synced {len(reactions)} preferences for user {user_id}")
            else:
                logger.error(f"Failed to sync preferences for user {user_id}")

            return success

        except Exception as e:
            logger.error(f"Error syncing preferences for user {user_id}: {e}")
            logger.error(traceback.format_exc())
            return False

    def sync_all_users_preferences(self, days_back: int = 2) -> dict[str, bool]:
        """
        Synchronize preferences for all users with configured repositories

        Args:
            days_back: Number of days to look back for reactions

        Returns:
            Dictionary mapping user_id to sync success status
        """
        results = {}

        try:
            # Get all users with repository configurations
            from src.db import db

            with db.session() as session:
                users_with_repos = (
                    session.query(UserSetting).filter(UserSetting.repo_url.isnot(None)).all()
                )

            logger.info(f"Starting preference sync for {len(users_with_repos)} users")

            for user_setting in users_with_repos:
                user_id = user_setting.id
                try:
                    success = self.sync_user_preferences(user_id, days_back)
                    results[user_id] = success
                except Exception as e:
                    logger.error(f"Failed to sync preferences for user {user_id}: {e}")
                    results[user_id] = False

            logger.info(
                f"Preference sync completed. Success: {sum(results.values())}, Failed: {len(results) - sum(results.values())}"
            )

        except Exception as e:
            logger.error(f"Error during bulk preference sync: {e}")
            logger.error(traceback.format_exc())

        return results
