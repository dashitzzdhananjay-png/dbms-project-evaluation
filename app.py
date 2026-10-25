import streamlit as st
import sqlite3
import pandas as pd

# 1. Database Connection & Auto-Setup (SQLite)
def init_db():
    conn = sqlite3.connect("project_eval_v2.db")
    c = conn.cursor()
    c.execute("PRAGMA foreign_keys = ON;")

    # Normalized Tables Create Karna
    c.executescript("""
    CREATE TABLE IF NOT EXISTS Faculty (
        faculty_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        department TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS Project_Groups (
        group_id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_name TEXT UNIQUE NOT NULL,
        guide_id INTEGER,
        FOREIGN KEY (guide_id) REFERENCES Faculty(faculty_id)
    );

    CREATE TABLE IF NOT EXISTS Students (
        student_id INTEGER PRIMARY KEY AUTOINCREMENT,
        roll_no TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        department TEXT NOT NULL,
        semester TEXT NOT NULL,
        group_id INTEGER,
        FOREIGN KEY (group_id) REFERENCES Project_Groups(group_id)
    );

    CREATE TABLE IF NOT EXISTS Projects (
        project_id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER UNIQUE,
        title TEXT NOT NULL,
        domain TEXT NOT NULL,
        status TEXT DEFAULT 'Pending',
        FOREIGN KEY (group_id) REFERENCES Project_Groups(group_id)
    );

    CREATE TABLE IF NOT EXISTS Milestones (
        milestone_id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        deadline TEXT NOT NULL,
        max_marks INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS Submissions (
        submission_id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER NOT NULL,
        milestone_id INTEGER NOT NULL,
        github_or_doc_link TEXT NOT NULL,
        submitted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        is_late INTEGER DEFAULT 0,
        FOREIGN KEY (project_id) REFERENCES Projects(project_id),
        FOREIGN KEY (milestone_id) REFERENCES Milestones(milestone_id)
    );

    CREATE TABLE IF NOT EXISTS Evaluations (
        eval_id INTEGER PRIMARY KEY AUTOINCREMENT,
        submission_id INTEGER UNIQUE NOT NULL,
        evaluator_id INTEGER NOT NULL,
        marks_obtained INTEGER,
        remarks TEXT,
        evaluated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (submission_id) REFERENCES Submissions(submission_id),
        FOREIGN KEY (evaluator_id) REFERENCES Faculty(faculty_id)
    );

    -- DBMS FEATURE 1: SQL TRIGGER (Late Submission Check)
    CREATE TRIGGER IF NOT EXISTS check_late_submission
    AFTER INSERT ON Submissions
    FOR EACH ROW
    BEGIN
        UPDATE Submissions
        SET is_late = CASE
            WHEN NEW.submitted_at > (SELECT deadline FROM Milestones WHERE milestone_id = NEW.milestone_id)
            THEN 1 ELSE 0
        END
        WHERE submission_id = NEW.submission_id;
    END;

    -- DBMS FEATURE 2: SQL VIEW (Final Grade Sheet with Student Details)
    CREATE VIEW IF NOT EXISTS Final_Grade_View AS
    SELECT 
        st.roll_no AS 'Roll No',
        st.name AS 'Student Name',
        st.department AS 'Department',
        pg.group_name AS 'Group Name',
        p.title AS 'Project Title',
        m.title AS 'Milestone',
        s.github_or_doc_link AS 'Submission Link',
        CASE WHEN s.is_late = 1 THEN 'Late' ELSE 'On Time' END AS 'Status',
        COALESCE(e.marks_obtained, 0) AS 'Marks Obtained',
        m.max_marks AS 'Max Marks',
        COALESCE(e.remarks, 'Pending Evaluation') AS 'Remarks'
    FROM Submissions s
    JOIN Projects p ON s.project_id = p.project_id
    JOIN Project_Groups pg ON p.group_id = pg.group_id
    JOIN Students st ON st.group_id = pg.group_id
    JOIN Milestones m ON s.milestone_id = m.milestone_id
    LEFT JOIN Evaluations e ON s.submission_id = e.submission_id;
    """)

    # Starter Faculty & Milestones Data (Sirf Pehli Baar)
    c.execute("SELECT COUNT(*) FROM Faculty")
    if c.fetchone()[0] == 0:
        c.execute("""
            INSERT INTO Faculty (name, email, department) VALUES 
            ('Dr. A. Sharma', 'sharma@nist.edu', 'CSE'), 
            ('Prof. R. Das', 'das@nist.edu', 'CSE'),
            ('Dr. S. Mohanty', 'mohanty@nist.edu', 'ECE')
        """)
        c.execute("""
            INSERT INTO Milestones (title, deadline, max_marks) VALUES 
            ('1. Synopsis & ER Diagram', '2026-12-15 23:59:59', 20), 
            ('2. Mid-Term Prototype', '2026-12-30 23:59:59', 30), 
            ('3. Final Report (Past Deadline Test)', '2026-01-01 23:59:59', 50)
        """)
        conn.commit()

    return conn

conn = init_db()
cursor = conn.cursor()

# 2. Streamlit Frontend UI
st.set_page_config(page_title="DBMS Project Evaluation System", layout="wide")
st.title("🎓 Project Submission & Evaluation System")

role = st.sidebar.radio("Navigation Menu", [
    "👨‍💻 Student Portal", 
    "👩‍🏫 Faculty Portal", 
    "📊 Final Grade Sheet (SQL View)", 
    "🗄️ View Raw Database Tables"
])

# ================= STUDENT PORTAL =================
if role == "👨‍💻 Student Portal":
    st.header("Student Registration & Submission Dashboard")
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("1. Student & Project Registration")
        
        # Student Personal Details
        student_name = st.text_input("Full Name (e.g., Dhananjay Dash)")
        roll_no = st.text_input("Roll Number (e.g., 202520660)")
        
        c1, c2 = st.columns(2)
        with c1:
            dept = st.selectbox("Department / Branch", ["CSE", "IT", "ECE", "EEE", "Mechanical", "Civil"])
        with c2:
            sem = st.selectbox("Semester", ["3rd Sem", "4th Sem", "5th Sem", "6th Sem", "7th Sem", "8th Sem"])

        st.markdown("---")
        # Group & Project Details
        group_name = st.text_input("Create / Enter Group Name (e.g., Team Alpha)")
        
        faculties = cursor.execute("SELECT faculty_id, name, department FROM Faculty").fetchall()
        fac_dict = {f"{f[1]} ({f[2]})": f[0] for f in faculties}
        sel_guide = st.selectbox("Select Faculty Guide", list(fac_dict.keys()))
        
        title = st.text_input("Project Title")
        domain = st.selectbox("Project Domain", ["DBMS / Web App", "AI / ML", "Data Structures / C", "IoT", "Cybersecurity"])

        if st.button("Register Student & Project", type="primary"):
            if student_name and roll_no and group_name and title:
                try:
                    # Check if group already exists, else create it
                    cursor.execute("SELECT group_id FROM Project_Groups WHERE group_name = ?", (group_name,))
                    row = cursor.fetchone()
                    if row:
                        gid = row[0]
                    else:
                        cursor.execute("INSERT INTO Project_Groups (group_name, guide_id) VALUES (?, ?)", (group_name, fac_dict[sel_guide]))
                        gid = cursor.lastrowid

                    # Insert Student Details
                    cursor.execute("""
                        INSERT INTO Students (roll_no, name, department, semester, group_id) 
                        VALUES (?, ?, ?, ?, ?)
                    """, (roll_no, student_name, dept, sem, gid))

                    # Insert Project Proposal (if not already submitted by this group)
                    cursor.execute("SELECT project_id FROM Projects WHERE group_id = ?", (gid,))
                    if not cursor.fetchone():
                        cursor.execute("INSERT INTO Projects (group_id, title, domain) VALUES (?, ?, ?)", (gid, title, domain))

                    conn.commit()
                    st.success(f"Registered! {student_name} ({roll_no}) aur Project '{title}' save ho gaya. Ab Faculty Portal se Approve karein!")
                except sqlite3.IntegrityError as e:
                    st.error(f"Error: Yeh Roll Number ({roll_no}) pehle se registered hai!")
            else:
                st.warning("Please fill all details (Name, Roll No, Group Name, and Project Title) before registering!")

    with col2:
        st.subheader("2. Upload Milestone Link")
        approved_projs = cursor.execute("""
            SELECT p.project_id, p.title, pg.group_name 
            FROM Projects p 
            JOIN Project_Groups pg ON p.group_id = pg.group_id 
            WHERE p.status = 'Approved'
        """).fetchall()
        milestones = cursor.execute("SELECT milestone_id, title, deadline FROM Milestones").fetchall()

        if not approved_projs:
            st.info("Koi Approved Project nahi mila. Pehle Left side mein Register karein aur Faculty Portal se Approve karein.")
        else:
            p_map = {f"{p[1]} ({p[2]})": p[0] for p in approved_projs}
            m_map = {f"{m[1]} (Deadline: {m[2]})": m[0] for m in milestones}

            sel_p = st.selectbox("Select Approved Project", list(p_map.keys()))
            sel_m = st.selectbox("Select Milestone", list(m_map.keys()))
            link = st.text_input("GitHub Link / Google Drive Report Link")

            if st.button("Submit Milestone"):
                if link:
                    cursor.execute("INSERT INTO Submissions (project_id, milestone_id, github_or_doc_link) VALUES (?, ?, ?)", (p_map[sel_p], m_map[sel_m], link))
                    conn.commit()
                    st.success("Submitted! (SQL Trigger ne check kar liya ki submission On-Time hai ya Late).")
                else:
                    st.warning("Link daalna zaroori hai.")

        st.markdown("---")
        st.subheader("👥 Registered Students List")
        df_stu = pd.read_sql_query("""
            SELECT s.roll_no AS 'Roll No', s.name AS 'Name', s.department AS 'Branch', 
                   s.semester AS 'Sem', pg.group_name AS 'Group'
            FROM Students s
            LEFT JOIN Project_Groups pg ON s.group_id = pg.group_id
        """, conn)
        if not df_stu.empty:
            st.dataframe(df_stu, use_container_width=True)
        else:
            st.caption("Abhi tak koi student register nahi hua hai.")

# ================= FACULTY PORTAL =================
elif role == "👩‍🏫 Faculty Portal":
    st.header("Faculty Evaluation Dashboard")
    tab1, tab2 = st.tabs(["✅ Approve Project Proposals", "📝 Grade Submissions"])

    with tab1:
        df_p = pd.read_sql_query("""
            SELECT p.project_id AS 'ID', pg.group_name AS 'Group', 
                   GROUP_CONCAT(s.name || ' (' || s.roll_no || ')', ', ') AS 'Students',
                   s.department AS 'Branch', p.title AS 'Project Title', p.domain AS 'Domain', p.status AS 'Status'
            FROM Projects p 
            JOIN Project_Groups pg ON p.group_id = pg.group_id
            LEFT JOIN Students s ON s.group_id = pg.group_id
            GROUP BY p.project_id
        """, conn)
        if not df_p.empty:
            st.dataframe(df_p, use_container_width=True)
            pid = st.selectbox("Select Project ID to Approve/Reject", df_p['ID'].tolist())
            new_st = st.selectbox("Select Status", ["Approved", "Rejected"])
            if st.button("Update Project Status"):
                cursor.execute("UPDATE Projects SET status = ? WHERE project_id = ?", (new_st, pid))
                conn.commit()
                st.success(f"Project ID {pid} status updated to {new_st}!")
                st.rerun()
        else:
            st.info("Abhi tak kisi student ne proposal register nahi kiya hai.")

    with tab2:
        df_s = pd.read_sql_query("""
            SELECT s.submission_id, pg.group_name AS 'Group', p.title AS Project, m.title AS Milestone, 
                   s.github_or_doc_link AS Link, 
                   CASE WHEN s.is_late = 1 THEN 'LATE' ELSE 'ON TIME' END AS Trigger_Status, m.max_marks
            FROM Submissions s
            JOIN Projects p ON s.project_id = p.project_id
            JOIN Project_Groups pg ON p.group_id = pg.group_id
            JOIN Milestones m ON s.milestone_id = m.milestone_id
            LEFT JOIN Evaluations e ON s.submission_id = e.submission_id
            WHERE e.eval_id IS NULL
        """, conn)

        if not df_s.empty:
            st.dataframe(df_s, use_container_width=True)
            sid = st.selectbox("Select Submission ID to Evaluate", df_s['submission_id'].tolist())
            marks = st.number_input("Enter Marks", min_value=0, max_value=100, value=18)
            rem = st.text_input("Remarks / Feedback", "Good database schema and working prototype.")
            if st.button("Save Marks"):
                cursor.execute("INSERT INTO Evaluations (submission_id, evaluator_id, marks_obtained, remarks) VALUES (?, 1, ?, ?)", (sid, marks, rem))
                conn.commit()
                st.success("Marks database mein save ho gaye!")
                st.rerun()
        else:
            st.info("Koi pending submission nahi hai evaluate karne ke liye.")

# ================= GRADE SHEET VIEW =================
elif role == "📊 Final Grade Sheet (SQL View)":
    st.header("Consolidated Student Result (Generated via SQL VIEW)")
    df_view = pd.read_sql_query("SELECT * FROM Final_Grade_View", conn)
    if not df_view.empty:
        st.dataframe(df_view, use_container_width=True)
    else:
        st.info("Jab submissions ho jayengi, tab yahan har student ke Roll No ke saath result dikhega.")

# ================= RAW TABLES (FOR VIVA DEMO) =================
elif role == "🗄️ View Raw Database Tables":
    st.header("Database Tables Inspector (For Viva Demonstration)")
    table_name = st.selectbox("Select Table to View Records", ["Students", "Project_Groups", "Projects", "Faculty", "Milestones", "Submissions", "Evaluations"])
    df_raw = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
    st.dataframe(df_raw, use_container_width=True)