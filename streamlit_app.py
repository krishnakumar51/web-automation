# streamlit_app.py
import streamlit as st
import requests
import os
import time

API_BASE = st.secrets.get("API_BASE", "http://localhost:8000")

st.set_page_config(page_title="Outlook Automation", page_icon="🤖", layout="wide")

st.title("🤖 Outlook Web Automation — Interactive UI")
st.markdown("---")

# Sidebar with instructions
with st.sidebar:
    st.header("📋 Instructions")
    st.markdown("""
    **How this works:**
    1. Enter a CURP and submit the job
    2. Browser will open and show the signup process step-by-step
    3. If CAPTCHA appears, solve it manually in the browser
    4. Click "Resume" here to continue automation
    5. Browser stays open until process completes
    
    **What to expect:**
    - ✅ Green borders = fields being filled
    - 🔴 Red borders = buttons being clicked  
    - ⚠️ Yellow banner = needs manual intervention
    - ✅ Green banner = success!
    """)

# Main content in two columns
col1, col2 = st.columns([1, 1])

with col1:
    st.header("🚀 Submit New Job")
    
    with st.form("submit_job"):
        curp = st.text_input("CURP (Mexican ID)", placeholder="e.g., CURP123456HDFZRL09")
        submitted = st.form_submit_button("🎯 Start Automation", use_container_width=True)
        
        if submitted:
            if not curp:
                st.error("❌ Please enter a CURP")
            else:
                with st.spinner("🚀 Starting automation..."):
                    try:
                        r = requests.post(f"{API_BASE}/jobs", json={"curp": curp})
                        if r.ok:
                            job = r.json()
                            st.success("✅ Job submitted successfully!")
                            st.info(f"**Job ID:** `{job['job_id']}`")
                            st.info(f"**Email:** `{job['email']}`")
                            st.balloons()
                        else:
                            st.error(f"❌ Error: {r.text}")
                    except Exception as e:
                        st.error(f"❌ Connection error: {e}")

with col2:
    st.header("🔍 Check Job Status")
    
    # Auto-refresh toggle
    auto_refresh = st.checkbox("🔄 Auto-refresh every 3 seconds", value=False)
    
    job_id = st.text_input("Job ID", placeholder="Enter job ID to check status")
    
    col2a, col2b = st.columns([3, 1])
    with col2a:
        check_clicked = st.button("🔍 Check Status", use_container_width=True)
    with col2b:
        if st.button("🔄"):
            st.rerun()
    
    if auto_refresh and job_id:
        time.sleep(3)
        st.rerun()

# Job status display
if (check_clicked or auto_refresh) and job_id:
    try:
        r = requests.get(f"{API_BASE}/jobs/{job_id}")
        if r.ok:
            job = r.json()
            
            # Status indicator
            status = job["status"]
            browser_open = job.get("browser_open", False)
            
            # Status badge
            if status == "completed":
                st.success(f"✅ **Status:** {status.upper()}")
            elif status == "waiting_for_human":
                st.warning(f"⚠️ **Status:** {status.upper()}")
            elif status == "failed":
                st.error(f"❌ **Status:** {status.upper()}")
            else:
                st.info(f"🔄 **Status:** {status.upper()}")
            
            # Browser status
            if browser_open:
                st.info("🌐 **Browser is OPEN** - You can interact with it!")
            else:
                st.info("🔒 **Browser is CLOSED**")
            
            # Account details
            st.subheader("📧 Account Details")
            account = job["created_account"]
            col_email, col_pass, col_status = st.columns([2, 2, 1])
            
            with col_email:
                st.text_input("Email", value=account["email"], disabled=True)
            with col_pass:
                st.text_input("Password", value=account["password"], type="password", disabled=True)
            with col_status:
                creation_status = account["creation_status"]
                if creation_status == "success":
                    st.success("✅ Created")
                elif "waiting" in creation_status:
                    st.warning("⏳ Waiting")
                elif creation_status == "failed":
                    st.error("❌ Failed")
                else:
                    st.info(f"🔄 {creation_status}")
            
            # CAPTCHA Screenshot
            if job.get("captcha_screenshot"):
                st.subheader("🖼️ Current Screenshot")
                screenshot_path = job["captcha_screenshot"]
                
                if os.path.exists(screenshot_path):
                    st.image(screenshot_path, caption="Current browser state", use_column_width=True)
                else:
                    st.warning("Screenshot file not found")
            
            # Action buttons
            st.subheader("🎮 Actions")
            
            button_col1, button_col2, button_col3 = st.columns([2, 2, 1])
            
            with button_col1:
                if status == "waiting_for_human" and browser_open:
                    if st.button("🔄 **Resume Automation**", use_container_width=True, type="primary"):
                        with st.spinner("🔄 Resuming automation..."):
                            try:
                                resume_r = requests.post(f"{API_BASE}/jobs/{job_id}/resume")
                                if resume_r.ok:
                                    st.success("✅ Automation resumed!")
                                    time.sleep(2)
                                    st.rerun()
                                else:
                                    st.error(f"❌ Resume failed: {resume_r.text}")
                            except Exception as e:
                                st.error(f"❌ Error: {e}")
                else:
                    st.button("🔄 Resume (Not Available)", disabled=True, use_container_width=True)
            
            with button_col2:
                if browser_open:
                    if st.button("🚪 Close Browser", use_container_width=True):
                        try:
                            close_r = requests.delete(f"{API_BASE}/jobs/{job_id}/browser")
                            if close_r.ok:
                                st.success("✅ Browser closed!")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error(f"❌ Close failed: {close_r.text}")
                        except Exception as e:
                            st.error(f"❌ Error: {e}")
                else:
                    st.button("🚪 Close Browser (Not Open)", disabled=True, use_container_width=True)
            
            with button_col3:
                if st.button("📋 Copy"):
                    st.code(f"Email: {account['email']}\nPassword: {account['password']}")
            
            # Detailed logs
            with st.expander("📋 Detailed Logs", expanded=False):
                if job["logs"]:
                    for i, log_entry in enumerate(reversed(job["logs"][-10:])):  # Show last 10 logs
                        timestamp = log_entry["timestamp"]
                        step = log_entry["step"]
                        success = log_entry["success"]
                        message = log_entry["message"]
                        
                        icon = "✅" if success else "❌"
                        st.text(f"{icon} [{timestamp}] {step}: {message}")
                else:
                    st.info("No logs yet...")
            
            # Progress indicator
            if status in ["running", "resuming"]:
                st.info("🔄 Process is running... Browser should be visible on your desktop!")
                
            elif status == "waiting_for_human":
                st.warning("""
                ⚠️ **MANUAL INTERVENTION NEEDED**
                
                1. 🔍 Look for the Microsoft Edge browser window on your desktop
                2. 🧩 Solve any CAPTCHA or verification challenges  
                3. ✋ Don't close the browser window
                4. 🔄 Click "Resume Automation" above when ready
                """)
                
            elif status == "completed":
                st.success("""
                🎉 **ACCOUNT CREATED SUCCESSFULLY!**
                
                ✅ Your Outlook account is ready to use
                📧 Email and password are shown above
                """)
                st.balloons()
                
            elif status == "failed":
                st.error("""
                ❌ **AUTOMATION FAILED**
                
                Check the logs above for details about what went wrong.
                You may need to try again or create the account manually.
                """)
        
        else:
            st.error("❌ Job not found or API error")
            
    except Exception as e:
        st.error(f"❌ Connection error: {e}")

# Footer with all jobs
st.markdown("---")
st.subheader("📊 All Jobs Overview")

try:
    all_jobs_r = requests.get(f"{API_BASE}/jobs")
    if all_jobs_r.ok:
        all_jobs = all_jobs_r.json()["jobs"]
        
        if all_jobs:
            # Create a table view
            job_data = []
            for job in all_jobs[-10:]:  # Show last 10 jobs
                job_data.append({
                    "Job ID": job["job_id"][:8] + "...",
                    "Email": job["email"],
                    "Status": job["status"],
                    "Browser": "🌐 Open" if job.get("browser_open") else "🔒 Closed",
                    "Account": job["creation_status"]
                })
            
            st.dataframe(job_data, use_container_width=True)
        else:
            st.info("No jobs yet")
    else:
        st.warning("Could not fetch job list")
except Exception as e:
    st.warning(f"Could not fetch jobs: {e}")

# Auto-refresh for active jobs
if auto_refresh:
    st.rerun()