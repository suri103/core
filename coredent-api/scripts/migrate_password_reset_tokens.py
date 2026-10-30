"""
Migration Script: Move password reset tokens from User model to separate table
This script migrates existing password reset tokens to the new PasswordResetToken table
"""

import asyncio
import sys
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, '.')

from sqlalchemy import select
from app.core.database import AsyncSessionLocal, engine
from app.models.user import User
from app.models.password_reset import PasswordResetToken


async def migrate_password_reset_tokens():
    """
    Migrate password reset tokens from User model to PasswordResetToken table.
    """
    print("Starting password reset token migration...")
    
    async with AsyncSessionLocal() as db:
        try:
            # Step 1: Create the new table if it doesn't exist
            print("Creating password_reset_tokens table...")
            async with engine.begin() as conn:
                # Import Base to create all tables
                from app.core.base import Base
                await conn.run_sync(Base.metadata.create_all)
            
            # Step 2: Find all users with password reset tokens
            result = await db.execute(
                select(User).where(User.password_reset_token.isnot(None))
            )
            users_with_tokens = result.scalars().all()
            
            print(f"Found {len(users_with_tokens)} users with existing password reset tokens")
            
            # Step 3: Migrate each token
            migrated_count = 0
            for user in users_with_tokens:
                # Skip if token is empty or expired
                if not user.password_reset_token or not user.password_reset_expires:
                    continue
                
                # Skip if token has already expired
                if user.password_reset_expires < datetime.utcnow():
                    print(f"Skipping expired token for user {user.email}")
                    continue
                
                # Create new PasswordResetToken record
                reset_token = PasswordResetToken(
                    user_id=user.id,
                    token=user.password_reset_token,
                    expires_at=user.password_reset_expires,
                    is_used=False,
                )
                db.add(reset_token)
                migrated_count += 1
            
            # Step 4: Clear password reset fields from User model
            # (Keep columns for backward compatibility, but clear values)
            for user in users_with_tokens:
                user.password_reset_token = None
                user.password_reset_expires = None
            
            # Step 5: Commit changes
            await db.commit()
            print(f"Successfully migrated {migrated_count} password reset tokens")
            
        except Exception as e:
            await db.rollback()
            print(f"Error during migration: {e}")
            raise


async def verify_migration():
    """
    Verify the migration was successful.
    """
    print("\nVerifying migration...")
    
    async with AsyncSessionLocal() as db:
        # Check PasswordResetToken table
        result = await db.execute(select(PasswordResetToken))
        tokens = result.scalars().all()
        print(f"PasswordResetToken entries: {len(tokens)}")
        
        # Check User table no longer has tokens
        result = await db.execute(
            select(User).where(User.password_reset_token.isnot(None))
        )
        users_with_tokens = result.scalars().all()
        print(f"Users still with tokens on User model: {len(users_with_tokens)}")
        
        if len(users_with_tokens) == 0:
            print("✅ Migration verified: All tokens moved to PasswordResetToken table")
        else:
            print("⚠️ Warning: Some users still have tokens on User model")


async def rollback_migration():
    """
    Rollback the migration (restore tokens to User model).
    """
    print("Rolling back migration...")
    
    async with AsyncSessionLocal() as db:
        try:
            # Get all password reset tokens
            result = await db.execute(
                select(PasswordResetToken).where(PasswordResetToken.is_used.is_(False))
            )
            tokens = result.scalars().all()
            
            restored_count = 0
            for token in tokens:
                # Find the user
                user_result = await db.execute(
                    select(User).where(User.id == token.user_id)
                )
                user = user_result.scalar_one_or_none()
                
                if user and token.expires_at > datetime.utcnow():
                    # Check if user already has a token
                    if not user.password_reset_token:
                        user.password_reset_token = token.token
                        user.password_reset_expires = token.expires_at
                        restored_count += 1
            
            await db.commit()
            print(f"Restored {restored_count} tokens to User model")
            
        except Exception as e:
            await db.rollback()
            print(f"Error during rollback: {e}")
            raise


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Password reset token migration")
    parser.add_argument(
        "--rollback",
        action="store_true",
        help="Rollback the migration instead of applying it"
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Only verify the migration, don't apply changes"
    )
    
    args = parser.parse_args()
    
    if args.verify:
        asyncio.run(verify_migration())
    elif args.rollback:
        asyncio.run(rollback_migration())
    else:
        asyncio.run(migrate_password_reset_tokens())
        asyncio.run(verify_migration())