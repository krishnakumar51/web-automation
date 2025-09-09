# test_browser.py
"""
Quick test script to verify the improved automation works.
Run this to test browser launching and visible field filling.
"""

import sys
import time
from pathlib import Path

# Add the app directory to path
sys.path.append(str(Path(__file__).parent))

from app.automation import run_signup
from app.logger import JobLogger
from app.curp_utils import gen_email_from_curp, gen_password

def test_automation():
    """Test the automation with a dummy CURP."""
    
    print("🚀 Testing improved Outlook automation...")
    print("=" * 50)
    
    # Generate test data
    test_curp = "TEST123456HDFZRL09"
    job_id = "test_job_001"
    email = gen_email_from_curp(test_curp)
    password = gen_password()
    
    print(f"📧 Test Email: {email}")
    print(f"🔐 Test Password: {password}")
    print(f"🆔 Job ID: {job_id}")
    print()
    
    # Create logger
    logger = JobLogger(job_id)
    
    print("🌐 Launching browser... (Edge will open visibly)")
    print("👀 Watch the browser - you should see:")
    print("   - Green borders around fields being filled")
    print("   - Red borders around buttons being clicked") 
    print("   - Slow, character-by-character typing")
    print("   - Pauses between actions")
    print()
    
    try:
        # Run automation
        result = run_signup(job_id, email, password, logger, headless=False)
        
        print("📊 RESULT:")
        print(f"   Status: {result['status']}")
        print(f"   Error: {result.get('error', 'None')}")
        print(f"   Screenshot: {'Yes' if result.get('screenshot') else 'No'}")
        
        if result["status"] == "waiting_for_human":
            print()
            print("⚠️  CAPTCHA/Protection detected!")
            print("   The browser should still be open.")
            print("   You can now:")
            print("   1. Solve any CAPTCHAs in the browser")
            print("   2. Use the Streamlit UI to resume")
            print("   3. Or run this script again to test resume")
        
        elif result["status"] == "completed":
            print()
            print("🎉 SUCCESS! Account creation completed!")
            
        elif result["status"] == "failed":
            print()
            print("❌ FAILED! Check the logs above.")
            
        # Print recent logs
        print()
        print("📋 Recent logs:")
        for log_entry in logger.entries[-5:]:  # Last 5 logs
            icon = "✅" if log_entry["success"] else "❌"
            print(f"   {icon} {log_entry['step']}: {log_entry['message']}")
            
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user")
        
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()

def test_resume():
    """Test the resume functionality."""
    
    job_id = input("Enter job ID to resume: ").strip()
    if not job_id:
        print("❌ No job ID provided")
        return
        
    print(f"🔄 Testing resume for job: {job_id}")
    
    from app.automation import resume_signup
    logger = JobLogger(job_id + "_resume")
    
    try:
        result = resume_signup(job_id, logger)
        
        print("📊 RESUME RESULT:")
        print(f"   Status: {result['status']}")
        print(f"   Error: {result.get('error', 'None')}")
        
        # Print logs
        print()
        print("📋 Resume logs:")
        for log_entry in logger.entries:
            icon = "✅" if log_entry["success"] else "❌"
            print(f"   {icon} {log_entry['step']}: {log_entry['message']}")
            
    except Exception as e:
        print(f"❌ Resume test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🤖 Outlook Automation Test Suite")
    print("=" * 40)
    print("1. Test new signup")
    print("2. Test resume functionality") 
    print("3. Exit")
    
    choice = input("\nEnter choice (1-3): ").strip()
    
    if choice == "1":
        test_automation()
    elif choice == "2":
        test_resume()
    elif choice == "3":
        print("👋 Goodbye!")
    else:
        print("❌ Invalid choice")