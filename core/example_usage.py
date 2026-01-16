"""
core/example_usage.py - Examples of using the Bug Exorcist Agent

This file demonstrates various ways to use the autonomous debugging agent.
"""

import asyncio
from core.agent import BugExorcistAgent, quick_fix


# Example 1: Simple error analysis
async def example_simple_fix():
    """Basic usage: analyze and fix a simple error"""
    
    error_message = """
Traceback (most recent call last):
  File "main.py", line 42, in calculate_average
    result = total / count
ZeroDivisionError: division by zero
"""
    
    code_snippet = """
def calculate_average(numbers):
    total = sum(numbers)
    count = len(numbers)
    result = total / count
    return result
"""
    
    agent = BugExorcistAgent(bug_id="BUG-001")
    result = await agent.analyze_error(error_message, code_snippet, file_path="main.py")
    
    print("🔍 Root Cause:", result['root_cause'])
    print("\n✨ Fixed Code:\n", result['fixed_code'])
    print("\n📝 Explanation:", result['explanation'])
    print(f"\n🎯 Confidence: {result['confidence']:.0%}")


# Example 2: Full workflow with streaming updates
async def example_full_workflow():
    """Complete workflow with real-time status updates"""
    
    error = """
TypeError: unsupported operand type(s) for +: 'int' and 'str'
  File "data_processor.py", line 15, in process_data
    total = item['value'] + accumulated
"""
    
    code = """
def process_data(items):
    accumulated = 0
    for item in items:
        total = item['value'] + accumulated
        accumulated = total
    return accumulated
"""
    
    agent = BugExorcistAgent(bug_id="BUG-002")
    
    print("🧟‍♂️ Starting Bug Exorcist Workflow...")
    print("=" * 50)
    
    async for update in agent.execute_full_workflow(
        error_message=error,
        code_snippet=code,
        file_path="data_processor.py"
    ):
        stage = update['stage']
        message = update['message']
        timestamp = update['timestamp']
        
        print(f"[{timestamp}] [{stage.upper()}] {message}")
        
        if 'data' in update and stage == 'analysis_complete':
            print(f"\n💡 Fixed Code Preview:\n{update['data']['fixed_code'][:200]}...\n")


# Example 3: Quick fix (one-liner)
async def example_quick_fix():
    """Fastest way to get a fix"""
    
    error = "IndexError: list index out of range"
    code = """
def get_first_item(items):
    return items[0]
"""
    
    fixed = await quick_fix(error, code)
    print("🚀 Quick Fixed Code:\n", fixed)


# Example 4: Real-world scenario with context
async def example_with_context():
    """Complex bug with additional context"""
    
    error = """
sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) no such table: users
[SQL: SELECT users.id, users.email FROM users WHERE users.id = ?]
"""
    
    code = """
from sqlalchemy.orm import Session
from .models import User

def get_user_by_id(db: Session, user_id: int):
    user = db.query(User).filter(User.id == user_id).first()
    return user
"""
    
    context = """
This is a FastAPI application with SQLAlchemy ORM.
The database models are defined in models.py.
The database initialization happens in database.py using Base.metadata.create_all().
The error occurs on application startup before tables are created.
"""
    
    agent = BugExorcistAgent(bug_id="BUG-003")
    result = await agent.analyze_error(
        error_message=error,
        code_snippet=code,
        file_path="app/crud.py",
        additional_context=context
    )
    
    print("🔍 Analysis Results:")
    print(f"Root Cause: {result['root_cause']}")
    print(f"\n✨ Solution:\n{result['fixed_code']}")
    print(f"\n📝 {result['explanation']}")


# Example 5: Batch processing multiple bugs
async def example_batch_processing():
    """Process multiple bugs in sequence"""
    
    bugs = [
        {
            "id": "BUG-101",
            "error": "AttributeError: 'NoneType' object has no attribute 'strip'",
            "code": "def clean_input(text): return text.strip().lower()"
        },
        {
            "id": "BUG-102", 
            "error": "KeyError: 'username'",
            "code": "def get_username(data): return data['username']"
        },
        {
            "id": "BUG-103",
            "error": "ValueError: invalid literal for int() with base 10: 'abc'",
            "code": "def parse_age(age_str): return int(age_str)"
        }
    ]
    
    print("🔄 Batch Processing Multiple Bugs...")
    print("=" * 50)
    
    for bug in bugs:
        agent = BugExorcistAgent(bug_id=bug['id'])
        result = await agent.analyze_error(bug['error'], bug['code'])
        
        print(f"\n✅ {bug['id']}: {result['root_cause'][:80]}...")
        print(f"   Confidence: {result['confidence']:.0%}")


async def main():
    """Run all examples"""
    print("🧟‍♂️ BUG EXORCIST - USAGE EXAMPLES")
    print("=" * 60)
    
    # Make sure OPENAI_API_KEY is set in environment
    import os
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  WARNING: OPENAI_API_KEY not set!")
        print("Set it with: export OPENAI_API_KEY='your-key-here'")
        return
    
    examples = [
        ("Simple Fix", example_simple_fix),
        ("Full Workflow", example_full_workflow),
        ("Quick Fix", example_quick_fix),
        ("With Context", example_with_context),
        ("Batch Processing", example_batch_processing)
    ]
    
    for name, example_func in examples:
        print(f"\n\n{'='*60}")
        print(f"📚 EXAMPLE: {name}")
        print('='*60)
        try:
            await example_func()
        except Exception as e:
            print(f"❌ Error in {name}: {e}")
        
        await asyncio.sleep(1)  # Brief pause between examples


if __name__ == "__main__":
    asyncio.run(main())