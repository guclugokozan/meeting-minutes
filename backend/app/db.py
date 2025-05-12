import aiosqlite
import json
from datetime import datetime
from typing import Optional, Dict
import logging
from contextlib import asynccontextmanager
import os # Added to access environment variables
import sqlite3

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_path: str = "meeting_minutes.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize the database with required tables"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Create meetings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS meetings (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            
            # Create transcripts table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS transcripts (
                    id TEXT PRIMARY KEY,
                    meeting_id TEXT NOT NULL,
                    transcript TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    summary TEXT,
                    action_items TEXT,
                    key_points TEXT,
                    FOREIGN KEY (meeting_id) REFERENCES meetings(id)
                )
            """)
            
            # Create summary_processes table (keeping existing functionality)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS summary_processes (
                    meeting_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    error TEXT,
                    result TEXT,
                    start_time TEXT,
                    end_time TEXT,
                    chunk_count INTEGER DEFAULT 0,
                    processing_time REAL DEFAULT 0.0,
                    metadata TEXT,
                    FOREIGN KEY (meeting_id) REFERENCES meetings(id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS transcript_chunks (
                    meeting_id TEXT PRIMARY KEY,
                    meeting_name TEXT,
                    transcript_text TEXT NOT NULL,
                    model TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    chunk_size INTEGER,
                    overlap INTEGER,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (meeting_id) REFERENCES meetings(id)
                )
            """)

            # Create settings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    id TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    whisperModel TEXT NOT NULL,
                    groqApiKey TEXT,
                    openaiApiKey TEXT,
                    anthropicApiKey TEXT,
                    ollamaApiKey TEXT
                )
            """)

            # Check if settings table is empty and insert default if so
            cursor.execute("SELECT COUNT(*) FROM settings WHERE id = '1'")
            # Use INSERT OR IGNORE to ensure the default settings row is created if it doesn't exist.
            # This is more atomic and simpler than checking count first.
            cursor.execute("""
                INSERT OR IGNORE INTO settings (id, provider, model, whisperModel)
                VALUES (?, ?, ?, ?)
            """, ('1', 'openai', 'gpt-4o-mini', 'whisper-1')) # Default provider is openai, model is gpt-4o-mini
            logger.info("Ensured default model configuration (using gpt-4o-mini for OpenAI) exists in settings table (used INSERT OR IGNORE).")
            # API keys from environment variables will be synchronized by sync_env_vars_to_db()
            # called during application startup in main.py.
            conn.commit()

    async def sync_env_vars_to_db(self):
        """Synchronize API keys from environment variables to the database."""
        logger.info("Attempting to synchronize environment variables to database settings.")
        made_changes = False
        try:
            async with self._get_connection() as conn:
                # OpenAI
                openai_key_env = os.getenv("OPENAI_API_KEY")
                if openai_key_env:
                    cursor = await conn.execute("UPDATE settings SET openaiApiKey = ? WHERE id = '1' AND (openaiApiKey IS NULL OR openaiApiKey != ?)", (openai_key_env, openai_key_env))
                    if cursor.rowcount > 0:
                        logger.info("Updated openaiApiKey in database from OPENAI_API_KEY environment variable via sync.")
                        made_changes = True
                else:
                    logger.warning("OPENAI_API_KEY environment variable not found during sync. openaiApiKey in database not updated by sync.")

                # Anthropic
                anthropic_key_env = os.getenv("ANTHROPIC_API_KEY")
                if anthropic_key_env:
                    cursor = await conn.execute("UPDATE settings SET anthropicApiKey = ? WHERE id = '1' AND (anthropicApiKey IS NULL OR anthropicApiKey != ?)", (anthropic_key_env, anthropic_key_env))
                    if cursor.rowcount > 0:
                        logger.info("Updated anthropicApiKey in database from ANTHROPIC_API_KEY environment variable via sync.")
                        made_changes = True
                else:
                    logger.warning("ANTHROPIC_API_KEY environment variable not found during sync. anthropicApiKey in database not updated by sync.")
                
                # Groq
                groq_key_env = os.getenv("GROQ_API_KEY")
                if groq_key_env:
                    cursor = await conn.execute("UPDATE settings SET groqApiKey = ? WHERE id = '1' AND (groqApiKey IS NULL OR groqApiKey != ?)", (groq_key_env, groq_key_env))
                    if cursor.rowcount > 0:
                         logger.info("Updated groqApiKey in database from GROQ_API_KEY environment variable via sync.")
                         made_changes = True
                else:
                    logger.warning("GROQ_API_KEY environment variable not found during sync. groqApiKey in database not updated by sync.")

                if made_changes:
                    await conn.commit()
                    logger.info("Committed API key updates to database during sync.")
                else:
                    logger.info("No API key changes to commit during sync; values were already up-to-date or env vars not set.")
        except Exception as e:
            logger.error(f"Error during sync_env_vars_to_db: {e}", exc_info=True)
            
    @asynccontextmanager
    async def _get_connection(self):
        """Get a new database connection"""
        conn = await aiosqlite.connect(self.db_path)
        try:
            yield conn
        finally:
            await conn.close()

    async def create_process(self, meeting_id: str) -> str:
        """Create a new process entry or update existing one and return its ID"""
        now = datetime.utcnow().isoformat()
        
        async with self._get_connection() as conn:
            # First try to update existing process
            await conn.execute(
                """
                UPDATE summary_processes 
                SET status = ?, updated_at = ?, start_time = ?, error = NULL, result = NULL
                WHERE meeting_id = ?
                """,
                ("PENDING", now, now, meeting_id)
            )
            
            # If no rows were updated, insert a new one
            if conn.total_changes == 0:
                await conn.execute(
                    "INSERT INTO summary_processes (meeting_id, status, created_at, updated_at, start_time) VALUES (?, ?, ?, ?, ?)",
                    (meeting_id, "PENDING", now, now, now)
                )
            
            await conn.commit()
        
        return meeting_id

    async def update_process(self, meeting_id: str, status: str, result: Optional[Dict] = None, error: Optional[str] = None, 
                           chunk_count: Optional[int] = None, processing_time: Optional[float] = None, 
                           metadata: Optional[Dict] = None):
        """Update a process status and result"""
        now = datetime.utcnow().isoformat()
        
        async with self._get_connection() as conn:
            update_fields = ["status = ?", "updated_at = ?"]
            params = [status, now]
            
            if result:
                update_fields.append("result = ?")
                params.append(json.dumps(result))
            if error:
                update_fields.append("error = ?")
                params.append(error)
            if chunk_count is not None:
                update_fields.append("chunk_count = ?")
                params.append(chunk_count)
            if processing_time is not None:
                update_fields.append("processing_time = ?")
                params.append(processing_time)
            if metadata:
                update_fields.append("metadata = ?")
                params.append(json.dumps(metadata))
            if status == 'COMPLETED' or status == 'FAILED':
                update_fields.append("end_time = ?")
                params.append(now)
                
            params.append(meeting_id)
            query = f"UPDATE summary_processes SET {', '.join(update_fields)} WHERE meeting_id = ?"
            await conn.execute(query, params)
            await conn.commit()

    async def save_transcript(self, meeting_id: str, transcript_text: str, model: str, model_name: str, 
                            chunk_size: int, overlap: int):
        """Save transcript data"""
        now = datetime.utcnow().isoformat()
        async with self._get_connection() as conn:
            # Attempt to fetch existing transcript text
            cursor = await conn.execute("SELECT transcript_text FROM transcript_chunks WHERE meeting_id = ?", (meeting_id,))
            row = await cursor.fetchone()
            
            existing_text = ""
            if row and row[0]:
                existing_text = row[0]
            
            # Append new transcript text to existing, ensuring a space or newline if existing_text is not empty
            # and new text doesn't naturally start with a space (common in HTML div structures)
            if existing_text and transcript_text:
                # A simple space might be enough, or consider if specific formatting like newline is better
                # For HTML content, just concatenating might be fine if each chunk is a self-contained div
                accumulated_transcript_text = existing_text + transcript_text
            else:
                accumulated_transcript_text = transcript_text or existing_text # Handles cases where one is empty

            # Use INSERT OR REPLACE to handle both new and existing meeting_ids
            # This simplifies logic compared to UPDATE then INSERT.
            # Note: If other fields should not be overwritten on replace, this strategy needs adjustment.
            # For transcript_chunks, overwriting model, model_name, chunk_size, overlap with latest values seems acceptable.
            await conn.execute("""
                INSERT OR REPLACE INTO transcript_chunks
                (meeting_id, transcript_text, model, model_name, chunk_size, overlap, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (meeting_id, accumulated_transcript_text, model, model_name, chunk_size, overlap, now))
            
            await conn.commit()

    async def update_meeting_name(self, meeting_id: str, meeting_name: str):
        """Update meeting name in both meetings and transcript_chunks tables"""
        now = datetime.utcnow().isoformat()
        async with self._get_connection() as conn:
            # Update meetings table
            await conn.execute("""
                UPDATE meetings
                SET title = ?, updated_at = ?
                WHERE id = ?
            """, (meeting_name, now, meeting_id))
            
            # Update transcript_chunks table
            await conn.execute("""
                UPDATE transcript_chunks
                SET meeting_name = ?
                WHERE meeting_id = ?
            """, (meeting_name, meeting_id))
            
            await conn.commit()

    async def get_transcript_data(self, meeting_id: str):
        """Get transcript data for a meeting"""
        async with self._get_connection() as conn:
            async with conn.execute("""
                SELECT t.*, p.status, p.result 
                FROM transcript_chunks t 
                JOIN summary_processes p ON t.meeting_id = p.meeting_id 
                WHERE t.meeting_id = ?
            """, (meeting_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return dict(zip([col[0] for col in cursor.description], row))
                return None

    async def save_meeting(self, meeting_id: str, title: str):
        """Save or update a meeting"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Check if meeting exists
                cursor.execute("SELECT id FROM meetings WHERE id = ? OR title = ?", (meeting_id, title))
                existing_meeting = cursor.fetchone()
                
                if not existing_meeting:
                    # Create new meeting
                    cursor.execute("""
                        INSERT INTO meetings (id, title, created_at, updated_at)
                        VALUES (?, ?, datetime('now'), datetime('now'))
                    """, (meeting_id, title))
                else:
                    # If we get here and meeting exists, throw error since we don't want duplicates
                    raise Exception(f"Meeting with ID {meeting_id} already exists")
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error saving meeting: {str(e)}")
            raise

    async def save_meeting_transcript(self, meeting_id: str, transcript: str, timestamp: str, summary: str = "", action_items: str = "", key_points: str = ""):
        """Save a transcript for a meeting"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Save transcript
                cursor.execute("""
                    INSERT INTO transcripts (
                        meeting_id, transcript, timestamp, summary, action_items, key_points
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (meeting_id, transcript, timestamp, summary, action_items, key_points))
                
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error saving transcript: {str(e)}")
            raise

    async def get_meeting(self, meeting_id: str):
        """Get a meeting by ID with all its transcripts"""
        try:
            async with self._get_connection() as conn:
                # Get meeting details
                cursor = await conn.execute("""
                    SELECT id, title, created_at, updated_at
                    FROM meetings
                    WHERE id = ?
                """, (meeting_id,))
                meeting = await cursor.fetchone()
                
                if not meeting:
                    return None
                
                # Get all transcripts for this meeting
                cursor = await conn.execute("""
                    SELECT transcript, timestamp
                    FROM transcripts
                    WHERE meeting_id = ?
                """, (meeting_id,))
                transcripts = await cursor.fetchall()
                
                return {
                    'id': meeting[0],
                    'title': meeting[1],
                    'created_at': meeting[2],
                    'updated_at': meeting[3],
                    'transcripts': [{
                        'id': meeting_id,
                        'text': transcript[0],
                        'timestamp': transcript[1]
                    } for transcript in transcripts]
                }
        except Exception as e:
            logger.error(f"Error getting meeting: {str(e)}")
            raise

    async def update_meeting_title(self, meeting_id: str, new_title: str):
        """Update a meeting's title"""
        now = datetime.utcnow().isoformat()
        async with self._get_connection() as conn:
            await conn.execute("""
                UPDATE meetings
                SET title = ?, updated_at = ?
                WHERE id = ?
            """, (new_title, now, meeting_id))
            await conn.commit()

    async def get_all_meetings(self):
        """Get all meetings with basic information"""
        async with self._get_connection() as conn:
            cursor = await conn.execute("""
                SELECT id, title, created_at
                FROM meetings
                ORDER BY created_at DESC
            """)
            rows = await cursor.fetchall()
            return [{
                'id': row[0],
                'title': row[1],
                'created_at': row[2]
            } for row in rows]

    async def delete_meeting(self, meeting_id: str):
        """Delete a meeting and all its associated data"""
        async with self._get_connection() as conn:
            try:
                # Delete from transcript_chunks
                await conn.execute("DELETE FROM transcript_chunks WHERE meeting_id = ?", (meeting_id,))
                
                # Delete from summary_processes
                await conn.execute("DELETE FROM summary_processes WHERE meeting_id = ?", (meeting_id,))
                
                # Delete from transcripts
                await conn.execute("DELETE FROM transcripts WHERE meeting_id = ?", (meeting_id,))
                
                # Delete from meetings
                await conn.execute("DELETE FROM meetings WHERE id = ?", (meeting_id,))
                
                await conn.commit()
                return True
            except Exception as e:
                logger.error(f"Error deleting meeting {meeting_id}: {str(e)}")
                return False

    async def get_model_config(self):
        """Get the current model configuration"""
        async with self._get_connection() as conn:
            cursor = await conn.execute("SELECT provider, model, whisperModel FROM settings WHERE id = '1'")
            row = await cursor.fetchone()
            return dict(zip([col[0] for col in cursor.description], row)) if row else None

    async def save_model_config(self, provider: str, model: str, whisperModel: str):
        """Save the model configuration"""
        async with self._get_connection() as conn:
            # Check if the configuration already exists
            cursor = await conn.execute("SELECT id FROM settings")
            existing_config = await cursor.fetchone()
            if existing_config:
                # Update existing configuration
                await conn.execute("""
                    UPDATE settings 
                    SET provider = ?, model = ?, whisperModel = ?
                    WHERE id = '1'    
                """, (provider, model, whisperModel))
            else:
                # Insert new configuration
                await conn.execute("""
                    INSERT INTO settings (id, provider, model, whisperModel)
                    VALUES (?, ?, ?, ?)
                """, ('1', provider, model, whisperModel))
            await conn.commit()


    async def save_api_key(self, api_key: str, provider: str):
        """Save the API key"""
        provider_list = ["openai", "claude", "groq", "ollama"]
        if provider not in provider_list:
            raise ValueError(f"Invalid provider: {provider}")
        if provider == "openai":
            api_key_name = "openaiApiKey"
        elif provider == "claude":
            api_key_name = "anthropicApiKey"
        elif provider == "groq":
            api_key_name = "groqApiKey"
        elif provider == "ollama":
            api_key_name = "ollamaApiKey"
        async with self._get_connection() as conn:
            await conn.execute(f"UPDATE settings SET {api_key_name} = ? WHERE id = '1'", (api_key,))
            await conn.commit()

    async def get_api_key(self, provider: str):
        """Get the API key"""
        provider_list = ["openai", "claude", "groq", "ollama"]
        if provider not in provider_list:
            raise ValueError(f"Invalid provider: {provider}")
        if provider == "openai":
            api_key_name = "openaiApiKey"
        elif provider == "claude":
            api_key_name = "anthropicApiKey"
        elif provider == "groq":
            api_key_name = "groqApiKey"
        elif provider == "ollama":
            api_key_name = "ollamaApiKey"
        async with self._get_connection() as conn:
            cursor = await conn.execute(f"SELECT {api_key_name} FROM settings WHERE id = '1'")
            row = await cursor.fetchone()
            # API keys should now be populated in the DB by _init_db() from environment variables.
            # So, we just return what's in the DB.
            api_key_value = row[0] if row and row[0] else None
            if not api_key_value:
                logger.warning(f"API key for provider '{provider}' not found in database for settings id '1'.")
            return api_key_value
        
    async def delete_api_key(self, provider: str):
        """Delete the API key"""
        provider_list = ["openai", "claude", "groq", "ollama"]
        if provider not in provider_list:
            raise ValueError(f"Invalid provider: {provider}")
        if provider == "openai":
            api_key_name = "openaiApiKey"
        elif provider == "claude":
            api_key_name = "anthropicApiKey"
        elif provider == "groq":
            api_key_name = "groqApiKey"
        elif provider == "ollama":
            api_key_name = "ollamaApiKey"
        async with self._get_connection() as conn:
            await conn.execute(f"UPDATE settings SET {api_key_name} = NULL WHERE id = '1'")
            await conn.commit()
            
   

