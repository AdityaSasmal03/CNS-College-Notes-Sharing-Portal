from flask import render_template, request, redirect, url_for, jsonify, flash, session
from models import Student, Teacher, Semester, Branch, Links
import configparser
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db as firebase_db
from datetime import datetime
import pandas as pd
import numpy as np
from googleapiclient.discovery import build
from google.oauth2 import service_account
from googleapiclient.http import MediaIoBaseUpload
import io
import fitz
from werkzeug.utils import secure_filename
import os
from flask import send_file
from transformers import pipeline
from fpdf import FPDF
import nltk
import smtplib
from email.message import EmailMessage

config = configparser.ConfigParser()
config.read('config.ini')
cred = credentials.Certificate("credentials.json")
# app should be initialised only once
try:
    firebase_admin.initialize_app(cred, {"databaseURL":config["firebase"]["database_url"]})
    firebase_db_ref = firebase_db.reference("/Gandhi_Institute_For_Technology")
except:
    pass

def register_routes(app, db):
    @app.route('/')
    def index():
        return render_template('index.html')
    
    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if request.method == "GET":            
            return render_template('register.html')
        elif request.method == "POST":
            name = request.form.get('name')
            password = request.form.get('password')
            existing_teacher = Teacher.query.filter_by(TeacherName=name).first()

            if existing_teacher:
                error = "Username already exists"
                return render_template('register.html', error=error)
            else:
                new_teacher = Teacher(TeacherName=name, Initials="T-", Password=password)
                db.session.add(new_teacher)
                db.session.commit()
                return render_template('register.html', error="Registered successfully")
    
    @app.route('/reigsterStudent', methods=['GET', 'POST'])
    def student_register():
        semesters = Semester.query.all()
        branches = Branch.query.all()
        branch_list = [{"BranchID": b.BranchID, "BranchName": b.BranchName, "SemesterID": b.SemesterID} for b in branches]
        if request.method == "GET":
            return render_template('studentReg.html', semesters=semesters, branches=branch_list)
        elif request.method == "POST":
            name = request.form.get("name")
            password = request.form.get("password")
            initials = request.form.get("initials")
            semester = request.form.get("semester")
            branch = request.form.get("branch")
            excel_file = request.files.get("excel_file")

            actual_branch = Branch.query.filter_by(BranchID=branch).first()
            actual_semester = Semester.query.filter_by(SemesterID=semester).first()
            basic_fields_blank = not (name and password and initials and semester and branch and semester != "0" and branch != "0")

            if basic_fields_blank and not excel_file:
                return render_template('studentReg.html', error="Please fill all the required fields or upload an Excel file.", semesters=semesters, branches=branch_list)
            
            elif excel_file:
                semesters1 = Semester.query.all()
                sem_list = [{"SemesterID": b.SemesterID, "SemesterName": b.SemesterName} for b in semesters1]
                result = register_students_through_excel(excel_file, sem_list, branch_list)

                if result == "done":
                    return render_template('studentReg.html', error=result, semesters=semesters, branches=branch_list)
                elif result == "Wrong data format":
                    return render_template('studentReg.html', error=result, semesters=semesters, branches=branch_list)
                else:
                    return render_template("show_error.html", elist=result)
            
            elif not basic_fields_blank and actual_branch and actual_semester:
                existing_student = Student.query.filter_by(
                StudentName=name,
                Initials=initials,
                Branch=actual_branch.BranchName,
                Semester=actual_semester.SemesterName
                ).first()

                if existing_student:
                    error = "Student already exists"
                    return render_template('studentReg.html', error=error, semesters=semesters, branches=branch_list)
                else:
                    try:
                        new_student = Student(
                        StudentName=name,
                        Password=password,
                        Initials=initials,
                        Branch=actual_branch.BranchName,
                        Semester=actual_semester.SemesterName
                        )
                        db.session.add(new_student)
                        db.session.commit()

                        return render_template('studentReg.html', error="Student registered successfully", semesters=semesters, branches=branch_list)
                    except Exception as e:
                        db.session.rollback()
                        error = f"An error occurred during registration: {str(e)}"
                        return render_template('studentReg.html', error=error, semesters=semesters, branches=branch_list)
            
            else:
                return render_template('studentReg.html', error="An error occurred during registration.", semesters=semesters, branches=branch_list)


    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == "GET":
            return render_template('login.html')
        elif request.method == "POST":
            username = request.form.get('username')
            password = request.form.get('password')
            segregator = ""
            try:
               segregator = username.split('-')               
               id = segregator[1]
               type = segregator[0]
            except:
                return render_template('login.html', error='Invalid username format')
            affiliation = ""
            try:
                if type == "T" :
                    # teacher
                    affiliation = "teacher"
                    user = Teacher.query.filter_by(T_ID=id).first()
                    if user:
                        if user.Password == password:
                            session['user'] = "teacher"
                            session["name"] = user.TeacherName
                            session["id"] = user.T_ID
                            session["initials"] = user.Initials
                            session["password"] = user.Password
                            session["email"] = user.Email
                            return redirect(url_for('teacher'))
                        else:
                            return render_template('login.html', error='Invalid password')
                    else:
                        return render_template('login.html', error='Invalid username ... please register first')
                elif type == "ADMIN":
                    # admin
                    affiliation = "admin"
                    user = Teacher.query.filter_by(T_ID=id).first()
                    if user:
                        if user.Password == password:
                            session["user"] = "admin"
                            session["name"] = user.TeacherName
                            session["id"] = user.T_ID
                            session["initials"] = user.Initials
                            session["password"] = user.Password
                            session["email"] = user.Email
                            return redirect(url_for('admin'))
                        else:
                            return render_template('login.html', error='Invalid password')
                    else:
                        return render_template('login.html', error='Invalid username ... please register first')
                elif type.startswith("S"):
                    # student                    
                    user = Student.query.filter_by(S_ID=id).first()
                    if type+"-" != user.Initials:
                        return render_template('login.html', error='Invalid username ... please register first')
                    if user:
                        affiliation = "student"
                        if user.Password == password:
                            session["user"] = "student"
                            session["name"] = user.StudentName
                            session["id"] = user.S_ID
                            session["branch"] = user.Branch
                            session["semester"] = user.Semester
                            session["role"] = user.Role
                            session["initials"] = user.Initials
                            session["password"] = user.Password
                            session["email"] = user.Email
                            return redirect(url_for('student'))
                        else:
                            return render_template('login.html', error='Invalid password')
                    else:
                        return render_template('login.html', error='Invalid username ... please register first')
                else:
                    return render_template('login.html', error='Invalid username format')
                    
            except:
                return render_template('login.html', error='Invalid username format')


    @app.route('/student', methods=['GET', 'POST'])
    def student():
        if request.method == "GET":
            if 'user' in session:
                if session.get('user') != "student":
                    return redirect(url_for('login'))
                
                student_data = {
                    "name": session["name"],
                    "branch": session["branch"],
                    "semester": session["semester"],
                    "initials": session["initials"],
                    "id": session["id"],
                    "password": session["password"],
                    "role": session["role"]
                }
                ref = firebase_db.reference("/Gandhi_Institute_For_Technology")
                x = firebase_db_ref.get().keys()
                common_group_data_for_html = []
                individual_group_data_for_html = []
                for i in x:
                    if(i == "common"):
                        d = ref.child(i).get()
                        if d:
                            dkeys = d.keys()
                            for j in dkeys:
                                da = ref.child(i).child(j).get()
                                if da and "data" in da and "members" in da["data"]:
                                    members = ["ALL"] if da["data"]["members"] == "ALL" else [m.lower() for m in da["data"]["members"]]                                    
                                    can_access_common = False
                                    can_edit = False
                                    if("ALL" in members):
                                        can_access_common = True
                                        can_edit = False
                                    else:
                                        for m in members:
                                            can_edit = False
                                            if m.lower() in str(session['branch']).lower() or m.lower() in str(session['semester']).lower():
                                                if(session['role'] == ""):
                                                    can_edit = False
                                                else:
                                                   can_edit = True
                                                can_access_common = True
                                                break
                                            else:
                                                can_edit = False
                                    groupname = da["data"].get("groupname")
                                    created_by = da["data"].get("created_by")
                                    created_on = da["data"].get("created_on")
                                    if groupname and created_by and created_on:
                                        temp = {
                                            "members": members,
                                            "groupname": groupname,
                                            "created_by": created_by,
                                            "created_on": created_on,
                                            "can_access": can_access_common,
                                            "can_edit": can_edit
                                        }
                                        common_group_data_for_html.append(temp)                     

                    elif(i == "house"):                        
                        d = ref.child(i).get()
                        if d:
                            dkeys = d.keys()
                            for j in dkeys:
                                da = ref.child(i).child(j).get()
                                dakeys = da.keys()
                                for k in dakeys:
                                    dataref1 = ref.child(i).child(j).child(k).get()
                                    data1 = dataref1["data"]
                                    ind_access = False
                                    if(session["branch"].lower() == data1["branch"].lower() and session["semester"].lower() == data1["semester"].lower()):
                                        ind_access = True

                                    test_role = session["role"]                                    
                                    temp = {
                                    "branch": data1["branch"],
                                    "groupname": data1["groupname"],
                                    "created_by": data1["created_by"],
                                    "created_on": data1["created_on"],
                                    "semester": data1["semester"],
                                    "can_access": ind_access,                                    
                                    }
                                    individual_group_data_for_html.append(temp)
                    
                    elif(i == "years"):                        
                        year_can_edit = False
                        d = ref.child(i).get()
                        if d:
                            dkeys = d.keys()
                            for j in dkeys:
                                da = ref.child(i).child(j).get()
                                dakeys = da.keys()
                                for k in dakeys:
                                    dataref = ref.child(i).child(j).child(k).get()
                                    data2 = dataref["data"]
                                    ind_access = False
                                    if(session["branch"].lower() == data2["branch"].lower() and session["semester"].lower() == data2["semester"].lower()):
                                        ind_access = True
                                    
                                    
                                    temp = {
                                    "branch": data2["branch"],
                                    "groupname": data2["groupname"],
                                    "created_by": data2["created_by"],
                                    "created_on": data2["created_on"],
                                    "semester": data2["semester"],
                                    "can_access": ind_access,
                                    "can_edit": year_can_edit
                                    }
                                    individual_group_data_for_html.append(temp)

                return render_template('student.html', user=session["user"], common_groups=common_group_data_for_html, individual_groups=individual_group_data_for_html,can_edit=can_edit, student_data=student_data)
            return redirect(url_for('login'))

    @app.route('/teacher', methods=['GET', 'POST'])
    def teacher():
        if request.method == "GET":
            if 'user' in session:
                if session.get('user') != "teacher":
                    return redirect(url_for('login'))
                return render_template('teacher.html', user=session["user"])
            return render_template('teacher.html')


    @app.route('/admin', methods=['GET', 'POST'])
    def admin():
        if request.method == "GET":
            if 'user' in session:
                if session.get('user') != "admin":
                    return redirect(url_for('login'))
                return render_template('admin.html', user=session["user"])
            return render_template('admin.html')
    

    @app.route('/create_section', methods=['GET', 'POST'])
    def create_section():
        semester = Semester.query.all()
        branch = Branch.query.all()
        branch_list = [{"BranchID": b.BranchID, "BranchName": b.BranchName, "SemesterID": b.SemesterID} for b in branch]
        members = ["ALL", "CSE", "ECE", "EEE", "MECH", "CIVIL", "AGRIL", "DIPLOMA"]
        for sem in semester:
            members.append(sem.SemesterName + " semester")
        if request.method == "GET":
            if 'user' in session:
                if session.get('user') == "student":
                    return redirect(url_for('login'))
                return render_template('create_section.html', user=session["user"], semesters=semester, branches=branch_list, members=members)
            return redirect(url_for('login'))
        elif request.method == "POST":
            if "common" in request.form:
                members_html = request.form.getlist("members")
                groupname = request.form.get("groupName")

                if members_html == "0" or members_html == "" or members_html == None or groupname == "" or groupname == None or members_html == []:
                    return render_template('create_section.html', error="Fill all required fields", user=session["user"], semesters=semester, branches=branch_list, members=members)
                
                else:
                    try:
                        members_html = "ALL" if "ALL" in members_html else members_html
                        group_created_on1 = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                        link_ref = "/Gandhi_Institute_For_Technology/common"
                        ref = firebase_db.reference(link_ref)
                        common_dict = ref.get()

                        can_pass = True
                        for groups in common_dict.keys():
                            if groups.lower() == groupname.lower():
                                can_pass = False                        

                        coms_ref = firebase_db_ref.child('common')                  
                        coms_node = coms_ref.child(groupname)
                        
                        if(can_pass == False):
                            return render_template('create_section.html', error="Group already exists", user=session["user"], semesters=semester, branches=branch_list, members=members)

                        data = {
                            "groupname": groupname,
                            "created_on": group_created_on1,
                            "members": members_html,
                            "created_by": session["name"], 
                            "contents": []     
                        }
                        coms_node.set({"data": data})

                        return render_template('create_section.html', error="Common group created successfully", user=session["user"], semesters=semester, branches=branch_list, members=members)
                    except Exception as e:
                        return render_template('create_section.html', error="An error occurred: " + str(e), user=session["user"], semesters=semester, branches=branch_list, members=members)

            elif "non-common" in request.form:
                semester_html = request.form.get("semester")
                branch_html = request.form.get("branch")

                if semester_html == "0" or branch_html == "0" or semester_html == "" or branch_html == "" or semester_html == None or branch_html == None:
                    return render_template('create_section.html', error="Fill all required fields", user=session["user"], semesters=semester, branches=branch_list, members=members)
                
                else:
                    actual_branch = Branch.query.filter_by(BranchID=branch_html).first()
                    actual_semester = Semester.query.filter_by(SemesterID=semester_html).first()

                    groupname1 = actual_branch.BranchName + "_" + actual_semester.SemesterName + "_semester"
                    group_created_on = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    if(actual_semester.SemesterName == "1st" or actual_semester.SemesterName == "2nd"):
                        try:
                            house_ref = firebase_db_ref.child('house')                        
                            sem_node = house_ref.child(actual_semester.SemesterName)
                            if(sem_node.child(actual_branch.BranchName).get()):
                                return render_template('create_section.html', error="Group already exists", user=session["user"], semesters=semester, branches=branch_list, members=members)
                            
                            data = {
                                "groupname": groupname1,
                                "created_on": group_created_on,
                                "branch": actual_branch.BranchName,
                                "semester": actual_semester.SemesterName,
                                "created_by": session["name"],
                                "subjects": [],
                                "subject_contents": []
                            }

                            sem_node.child(actual_branch.BranchName).set({"data": data})                        

                            return render_template('create_section.html', error="Group created successfully", user=session["user"], semesters=semester, branches=branch_list, members=members)
                        except Exception as e:
                            return render_template('create_section.html', error="An error occurred: " + str(e), user=session["user"], semesters=semester, branches=branch_list, members=members)
                    
                    elif(actual_semester.SemesterName == "3rd" or actual_semester.SemesterName == "4th" or actual_semester.SemesterName == "5th" or actual_semester.SemesterName == "6th" or actual_semester.SemesterName == "7th" or actual_semester.SemesterName == "8th"):
                        try:
                            house_ref = firebase_db_ref.child('years')                        
                            sem_node = house_ref.child(actual_semester.SemesterName)
                            if(sem_node.child(actual_branch.BranchName).get()):
                                return render_template('create_section.html', error="Group already exists", user=session["user"], semesters=semester, branches=branch_list, members=members)
                            
                            data = {
                                "groupname": groupname1,
                                "created_on": group_created_on,
                                "branch": actual_branch.BranchName,
                                "semester": actual_semester.SemesterName,
                                "created_by": session["name"],
                                "subjects": [],
                                "subject_contents": []                            
                            }

                            sem_node.child(actual_branch.BranchName).set({"data": data})                        

                            return render_template('create_section.html', error="Group created successfully", user=session["user"], semesters=semester, branches=branch_list, members=members)
                        except Exception as e:
                            return render_template('create_section.html', error="An error occurred: " + str(e), user=session["user"], semesters=semester, branches=branch_list, members=members)
                    
                    else:
                        return render_template('create_section.html', error="Invalid semester", user=session["user"], semesters=semester, branches=branch_list, members=members)

    @app.route('/enroll', methods=['GET', 'POST'])
    def add_branches():
        if 'user' in session:
            if session.get('user') != "teacher":
                return redirect(url_for('login'))
            
            # show all data from firebase
            teacher_data = {
                    "name": session["name"],
                    "id": session["id"],
                    "initials": session["initials"],
                    "password": session["password"]
                }
            if request.method == "GET":                
                ref = firebase_db.reference("/Gandhi_Institute_For_Technology")
                x = ref.get().keys()
                all_groups = []
                common_group_data_for_html = []
                individual_group_data_for_html = []
                house_members = []
                year_members = []
                for i in x:
                    if(i == "common"):
                        d = ref.child(i).get()
                        if d:
                            dkeys = d.keys()
                            for j in dkeys:
                                da = ref.child(i).child(j).get()
                                if da and "data" in da and "members" in da["data"]:
                                    members = ["ALL"] if da["data"]["members"] == "ALL" else da["data"]["members"]
                                    can_access_common = True
                                    can_edit = True
                                          
                                    groupname = da["data"].get("groupname")
                                    created_by = da["data"].get("created_by")
                                    created_on = da["data"].get("created_on")
                                    if groupname and created_by and created_on:
                                        temp = {
                                            "members": members,
                                            "groupname": groupname,
                                            "created_by": created_by,
                                            "created_on": created_on,
                                            "can_access": can_access_common,
                                        }
                                        common_group_data_for_html.append(temp)
                    
                    elif(i == "house"):
                        d = ref.child(i).get()
                        if d:
                            dkeys = d.keys()
                            for j in dkeys:
                                da = ref.child(i).child(j).get()
                                dakeys = da.keys()
                                for k in dakeys:
                                    data = ref.child(i).child(j).child(k).get()
                                    data = data["data"]
                                    ind_access = True                                    
                                    test_branch = data["branch"].lower()
                                    test_sems = data["semester"].lower()
                                    user = Student.query.filter_by(Branch=test_branch, Semester=test_sems).all()

                                    house_members = [
                                        {
                                            "name": u.StudentName,
                                            "id": u.S_ID,
                                            "initials": u.Initials,
                                            "password": u.Password,
                                            "role": u.Role,
                                            "branch": u.Branch,
                                            "semester": u.Semester
                                        }
                                        for u in user
                                    ]
                                    temp = {
                                    "branch": data["branch"],
                                    "groupname": data["groupname"],
                                    "created_by": data["created_by"],
                                    "created_on": data["created_on"],
                                    "semester": data["semester"],
                                    "can_access": ind_access,
                                    }
                                    individual_group_data_for_html.append(temp)
                    
                    elif(i == "years"):
                        d = ref.child(i).get()
                        if d:
                            dkeys = d.keys()
                            for j in dkeys:
                                da = ref.child(i).child(j).get()
                                dakeys = da.keys()
                                for k in dakeys:
                                    data = ref.child(i).child(j).child(k).get()
                                    data = data["data"]
                                    ind_access = True
                                    test_branch = data["branch"].lower()
                                    test_sems = data["semester"].lower()
                                    user = Student.query.filter_by(Branch=test_branch, Semester=test_sems).all()

                                    year_members = [
                                        {
                                            "name": u.StudentName,
                                            "id": u.S_ID,
                                            "initials": u.Initials,
                                            "password": u.Password,
                                            "role": u.Role,
                                            "branch": u.Branch,
                                            "semester": u.Semester
                                        }
                                        for u in user
                                        ]                                    
                                    temp = {
                                    "branch": data["branch"],
                                    "groupname": data["groupname"],
                                    "created_by": data["created_by"],
                                    "created_on": data["created_on"],
                                    "semester": data["semester"],
                                    "can_access": ind_access,
                                    }
                                    individual_group_data_for_html.append(temp)
                    
                return render_template('add_branches.html', user=session["user"], teacher_data=teacher_data, common_groups=common_group_data_for_html, can_edit=can_edit, individual_groups=individual_group_data_for_html, house_members=house_members, year_members=year_members)
            
            elif request.method == "POST":
                if "common_enroll" in request.form:
                    groupname_common = request.form.get("groupname_common")
                    common_members = request.form.get("members")
                    teacher_data_in_common = {
                        "name": session["name"],
                        "id": session["id"],
                        "initials": session["initials"],
                        "password": session["password"],
                        "groupname": groupname_common,
                        "members": common_members
                    }
                    ref1 = firebase_db.reference(f"/Gandhi_Institute_For_Technology/common/{groupname_common}/{teacher_data_in_common['name']}")
                    
                    if(ref1.get() == None):
                        try:
                            ref1.update({
                                "Teachername": teacher_data_in_common["name"],
                                "ID": teacher_data_in_common["id"],
                                "Groupname": teacher_data_in_common["groupname"],
                                "can_upload": True
                            })
                            flash("Enrolled successfully", "success")
                            return redirect(url_for("add_branches"))
                        except Exception as e:
                            flash(f"some error occured while entry: {e}", "error")
                            return redirect(url_for("add_branches"))
                    else:
                        flash("You are already in the group", "warning")
                        return redirect(url_for('add_branches'))                


                elif "enroll" in request.form:
                    teacher_id = request.form.get("teacher_id")
                    teacher_name = request.form.get("teacher_name")
                    branch_html = request.form.get("branch").lower()
                    semester_html = request.form.get("semester").lower()
                    try:
                        subject = request.form.get("subject").capitalize()
                    except:
                        flash("Fill all required fields", "error")
                        return redirect(url_for("add_branches"))
                    
                    if subject == "" or subject == None:
                        flash("Fill all required fields", "error")
                        return redirect(url_for("add_branches"))
                    
                    groupname_html = branch_html + "_" + semester_html + "_semester"

                    teacher_data = {
                        "teacher_id": teacher_id,
                        "teacher_name": teacher_name,
                        "branch": branch_html,
                        "semester": semester_html,
                        "subject": subject,
                        "groupname": groupname_html
                    }

                    if (semester_html == "1st" or semester_html == "2nd"):
                        type = "house"
                        ref1 = firebase_db.reference(f"/Gandhi_Institute_For_Technology/{type}/{semester_html}/{branch_html}/{subject}")
                        ref1.update(teacher_data)

                    elif (semester_html == "3rd" or semester_html == "4th" or semester_html == "5th" or semester_html == "6th" or semester_html == "7th" or semester_html == "8th"):
                        type = "years"
                        ref1 = firebase_db.reference(f"/Gandhi_Institute_For_Technology/{type}/{semester_html}/{branch_html}/{subject}")
                        ref1.update(teacher_data)

                    flash("Enrolled successfully", "success")
                    return redirect(url_for("add_branches"))
    

    @app.route('/show_sections', methods=["GET", "POST"])
    def show_sections():
        if 'user' in session:
            if session['user'] == "teacher":
                if request.method == "GET":                                        
                    return render_template("show_group_teacher.html")

                elif request.method == "POST":
                    type = request.form.get('group_type')
                    if(type == "common"):
                        common_ref = firebase_db.reference(f"/Gandhi_Institute_For_Technology/common")
                        get_common = common_ref.get()

                        teacher_data = []
                        contents = []

                        for ckeys in get_common.keys():
                            temp_ref = firebase_db.reference(f"/Gandhi_Institute_For_Technology/common/{ckeys}")
                            for i in temp_ref.get().keys():
                                j = temp_ref.get()
                                if i == session["name"]:
                                    t = {
                                        "teachername": j[i]["Teachername"],
                                        "ID": j[i]["ID"],
                                        "can_upload": j[i]["can_upload"],
                                        "Groupname": j[i]["Groupname"],
                                        "created_by": j["data"]["created_by"],
                                        "created_on": j["data"]["created_on"],
                                        "members": j["data"]["members"]
                                    }
                                    teacher_data.append(t)
                                elif i == "content":
                                    for ik in j[i].keys():
                                        cont = {
                                            "by": j[i][ik]["by"],
                                            "fileid": j[i][ik]["fileid"],
                                            "link": j[i][ik]["link"],
                                            "uploaded_on": j[i][ik]["uploaded_on"],
                                            "group": j[i][ik]["group"],
                                            "file_name": j[i][ik]["file_name"]
                                        }
                                        contents.append(cont)

                        return render_template("common_t.html", teacher_data=teacher_data, contents=contents)


                    elif(type == "non-common"):
                        teacher_data_indiv = []
                        contents_indiv = []

                        parent_url = f"/Gandhi_Institute_For_Technology"
                        ref = firebase_db.reference(parent_url)
                        noncoms = ref.get()

                        for t in noncoms.keys():
                            if (t != "common"):
                                    n_parent_url = parent_url + f"/{t}"
                                    r1 = firebase_db.reference(n_parent_url)
                                    go_inside_sem = r1.get()

                                    for s in go_inside_sem.keys():
                                        n1_parent_url = n_parent_url + f"/{s}"
                                        r2 = firebase_db.reference(n1_parent_url)
                                        go_inside_branch = r2.get()
                                        
                                        for b in go_inside_branch.keys():
                                            n2_parent_url = n1_parent_url + f"/{b}"
                                            r3 = firebase_db.reference(n2_parent_url)
                                            inside_each_branch = r3.get()
                                            
                                            for x in inside_each_branch.keys():
                                                if(x != "CR" and x != "data"):
                                                    if inside_each_branch[x]["teacher_name"] == session["name"]:
                                                        teach = {
                                                            "groupname": inside_each_branch[x]["groupname"],
                                                            "semester": inside_each_branch[x]["semester"],
                                                            "branch": inside_each_branch[x]["branch"],
                                                            "subject": inside_each_branch[x]["subject"],
                                                            "teacher_id": inside_each_branch[x]["teacher_id"],
                                                            "teacher_name": inside_each_branch[x]["teacher_name"]
                                                        }
                                                        teacher_data_indiv.append(teach)

                        return render_template("indiv_t.html", teacher_data=teacher_data_indiv, contents=contents_indiv)


            else:
                return redirect(url_for('login'))
        else:
            return redirect(url_for('login'))
        
    @app.route('/view_subject_details', methods=["GET", "POST"])
    def view_subject_details():
        if 'user' in session:
            if session["user"] == "teacher":
                groupname = request.form.get('groupname')
                branch = request.form.get('branch')
                semester = request.form.get('semester')
                subject = request.form.get('subject')
                type = "house" if semester == "1st" or semester == "2nd" else "years"

                group_info = {
                    "groupname": groupname,
                    "branch": branch,
                    "semester": semester,
                    "subject": subject
                }

                cr_id_link = f"/Gandhi_Institute_For_Technology/{type}/{semester}/{branch}/CR"
                ref = firebase_db.reference(cr_id_link)
                cr_id = int(ref.get()) 

                cr = Student.query.filter_by(S_ID=cr_id).first()
                cr_data = {
                    "name":cr.StudentName,
                    "role":cr.Role,
                    "id": cr.Initials + str(cr_id)
                }

                total_files = []
                main_par = "/Gandhi_Institute_For_Technology"
                construct_child_par = main_par + f"/{type}/{semester}/{branch}/{subject}/content"
                ref = firebase_db.reference(construct_child_par)
                c = ref.get()
                
                if c != None:
                    for keys in c.keys():
                        new_construct_child_par = construct_child_par + f"/{keys}"
                        r1 = firebase_db.reference(new_construct_child_par)
                        total_files.append(r1.get())


                return render_template("view_group_t.html", total_files=total_files, group_info=group_info, cr_data=cr_data)


            else:
                return redirect(url_for(login))
        else:
            return redirect(url_for(login))
    

    @app.route('/upload_drive_indiv', methods=["GET", "POST"])
    def upload_to_drive_indiv():
        if 'user' in session:
            if session['user'] == "teacher" and request.method == "POST":
                SCOPES = ["https://www.googleapis.com/auth/drive"]
                SERVICE_ACCOUNT_FILE = "service_account.json"
                PARENT_FOLDER_ID = config["drive"]["parent_folder_id"]
                creds = authenticate(SERVICE_ACCOUNT_FILE, SCOPES)
                file_to_upload = request.files.get('file')
                filename = request.form.get('filename')
                groupname = request.form.get('groupname')
                branch = request.form.get('branch')
                semester = request.form.get('semester')
                subject = request.form.get('subject')

                service = build('drive', 'v3', credentials=creds)

                now = datetime.now()
                timestamp_str = now.strftime("%Y-%m-%d %H-%M-%S")
                final_file_name = f"{filename}_{timestamp_str}_{groupname}_{subject}"

                file_metadata = {
                    'name':  final_file_name,
                    'parents': [PARENT_FOLDER_ID]
                }
                
                try:
                    media = io.BytesIO(file_to_upload.read())
                    media_body = MediaIoBaseUpload(media, mimetype=file_to_upload.content_type, resumable=True)

                    f = service.files().create(
                        body=file_metadata,
                        media_body=media_body,
                        fields='id'
                    ).execute()

                    file_id_to_push = f.get('id')
                    content_link = f"https://drive.google.com/file/d/{file_id_to_push}/view?usp=sharing"

                    if(semester == "1st" or semester == "2nd"):
                        ref = firebase_db.reference(f"/Gandhi_Institute_For_Technology/house/{semester}/{branch}/{subject}/content")
                        new_content_ref = ref.push()
                        new_content_ref.set({
                            "fileid": file_id_to_push,
                            "link": content_link,
                            "uploaded_on": timestamp_str,
                            "by": session["name"],
                            "group": groupname,
                            "file_name": final_file_name,
                            "branch": branch,
                            "semester": semester,
                            "subject": subject                    
                        })
                    
                    else:
                        ref = firebase_db.reference(f"/Gandhi_Institute_For_Technology/years/{semester}/{branch}/{subject}/content")
                        new_content_ref = ref.push()
                        new_content_ref.set({
                            "fileid": file_id_to_push,
                            "link": content_link,
                            "uploaded_on": timestamp_str,
                            "by": session["name"],
                            "group": groupname,
                            "file_name": final_file_name,
                            "branch": branch,
                            "semester": semester,
                            "subject": subject
                        }) 

                    flash('File uploaded successfully!', 'success')                    
                    try:
                        send_mail(content_link, semester, branch, subject, session["email"], session["name"])
                    except Exception as emailEX:
                        print("Email error: ",emailEX)
                    return redirect(url_for('show_sections'))

                except Exception as e:
                    flash(f"An error occurred: {e}", 'error')
                    return redirect(url_for('show_sections'))
            else:
                return redirect(url_for(login))
        else:
            return redirect(url_for(login))
                
    
    @app.route('/upload_drive', methods=["GET", "POST"])
    def upload_to_drive():
        SCOPES = ["https://www.googleapis.com/auth/drive"]
        SERVICE_ACCOUNT_FILE = "service_account.json"
        PARENT_FOLDER_ID = config["drive"]["parent_folder_id"]
        creds = authenticate(SERVICE_ACCOUNT_FILE, SCOPES)
        file_to_upload = request.files.get('file')
        filename = request.form.get('filename')
        groupname = request.form.get('groupname')
        service = build('drive', 'v3', credentials=creds)

        now = datetime.now()
        timestamp_str = now.strftime("%Y-%m-%d %H-%M-%S")
        final_file_name = f"{filename}_{timestamp_str}_{groupname}"

        file_metadata = {
            'name':  final_file_name,
            'parents': [PARENT_FOLDER_ID]
        }
        
        try:
            media = io.BytesIO(file_to_upload.read())
            media_body = MediaIoBaseUpload(media, mimetype=file_to_upload.content_type, resumable=True)

            f = service.files().create(
                body=file_metadata,
                media_body=media_body,
                fields='id'
            ).execute()

            file_id_to_push = f.get('id')
            content_link = f"https://drive.google.com/file/d/{file_id_to_push}/view?usp=sharing"

            ref = firebase_db.reference(f"/Gandhi_Institute_For_Technology/common/{groupname}/content")
            new_content_ref = ref.push()
            new_content_ref.set({
                "fileid": file_id_to_push,
                "link": content_link,
                "uploaded_on": timestamp_str,
                "by": session["name"],
                "group": groupname,
                "file_name": final_file_name
            })
            flash('File uploaded successfully!', 'success')
            return redirect(url_for('show_sections'))

        except Exception as e:
            flash(f"An error occurred: {e}", 'success')
            return redirect(url_for('show_sections'))

    
    def authenticate(SERVICE_ACCOUNT_FILE, SCOPES):
        creds = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        return creds


    @app.route('/show_group', methods=["GET", "POST"])
    def show_group():
        if 'user' in session:
            if session['user'] != "admin":
                group_type = request.form.get('type')
                group_name = request.form.get('groupname')
                group_branch = request.form.get('group_branch')
                group_semester = request.form.get('group_semester')
                created_by = request.form.get('created_by')
                created_on = request.form.get('created_on')
                can_access = request.form.get('can_access')
                student_id = request.form.get('student_id')
                student_name = request.form.get('student_name')
                student_branch = request.form.get('student_branch')
                student_semester = request.form.get('student_semester')
                student_role = request.form.get('student_role')
                members_str = request.form.get('members')
                members = members_str.split(',') if members_str else []

                teachers = []
                content_name = []
                content_urls = []
                subjects = []
                cr_id = ""
                cr_data = {}
                

                if(group_type == "common"):
                    teachers, content_name = show_commom_group_to_student(group_branch, group_semester, group_name)
                
                elif(group_type == "non-common"):
                    subjects, cr_id = show_individual_group_to_student(group_branch, group_semester)
                    cr = Student.query.filter_by(S_ID=cr_id).first()
                    cr_data = {
                        "name":cr.StudentName,
                        "role":cr.Role,
                        "id": cr_id
                    }

                return render_template('groupforstudent.html',
                                content_urls=content_urls,
                                type=group_type,
                                group_name=group_name,
                                group_branch=group_branch,
                                group_semester=group_semester,
                                created_by=created_by,
                                created_on=created_on,
                                can_access=can_access,
                                student_id=student_id,
                                student_name=student_name,
                                student_branch=student_branch,
                                student_semester=student_semester,
                                student_role=student_role,
                                members=members,
                                subjects=subjects,
                                cr_id=cr_id,
                                teachers=teachers,
                                content_names=content_name,
                                cr_data=cr_data
                                )
            else:
                return redirect(url_for('login'))
        else:
            return redirect(url_for('login'))

    @app.route('/back_admin')
    def back_admin():
        if 'user' in session:
            if session.get('user') == "student":
                return redirect(url_for('login'))
            elif session.get('user') == "teacher":
                return render_template('teacher.html', user=session["user"])
            return render_template('admin.html', user=session["user"])
        return redirect(url_for('login'))
    
    @app.route('/back_student')
    def back_student():
        if 'user' in session:
            if session.get('user') != "student":
                return redirect(url_for('login'))
            session.pop('user', None)
            return redirect(url_for('login'))
        return redirect(url_for('login'))
    
    @app.route('/back_student_group')
    def back_student_again():
        if 'user' in session:
            if session.get('user') != "student":
                return redirect(url_for('login'))
            return redirect(url_for('student'))
        return redirect(url_for('login'))
    
    @app.route('/back_teacher')
    def back_teacher():
        if 'user' in session:
            if session.get('user') != "teacher":
                return redirect(url_for('login'))
            return render_template('teacher.html', user=session["user"])
        return redirect(url_for('login'))
    
    @app.route('/back_to_page')
    def back_common():
        if 'user' in session:
            if session.get('user') == "teacher":
                return render_template('teacher.html', user=session["user"])
            elif session['user'] == "student":
                return redirect(url_for('login'))
            else:
                return render_template('admin.html', user=session["user"])

        return redirect(url_for('login'))

    @app.route('/logout')
    def logout():
        session.pop('user', None)
        return redirect(url_for('login'))
    
    @app.route('/show_students', methods=["GET", "POST"])
    def show_students():
        if 'user' in session:
            if session.get('user') == "student":
                return redirect(url_for('login'))
            
            all_student = Student.query.all()
            test = []

            for s in all_student:
                test.append({
                    f"{s.Branch}_{s.Semester}": [{
                        "Name": s.StudentName,
                        "ID": s.S_ID,
                        "Role": "" if s.Role == None else s.Role,
                        "Branch": s.Branch,
                        "Semester": s.Semester,
                        "Initials": s.Initials
                    }]
                })

            final_data_to_pass = group_by_student_branch_and_semester(test)            
            return render_template('show_student.html', user=session["user"], final_data=final_data_to_pass)
        return redirect(url_for('login'))
    
    @app.route('/appoint_cr', methods=["GET", "POST"])
    def appoint_cr():
        if request.method == "POST":
            # change value of Role
            id = request.form.get('student_id')
            user_by_id = Student.query.filter_by(S_ID=id).first()
            if user_by_id:
                current_user_branch = user_by_id.Branch
                current_user_semester = user_by_id.Semester

                same_batch_as_current_user = Student.query.filter(
                    Student.Branch == current_user_branch,
                    Student.Semester == current_user_semester
                ).all()
                try:
                    for user in same_batch_as_current_user:
                        user.Role = None                    
                    user_by_id.Role = "CR"
                    db.session.commit()
                    
                    if(current_user_semester == "1st" or current_user_semester == "2nd"):
                        house_ref = firebase_db.reference(f"/Gandhi_Institute_For_Technology/house/{current_user_semester}/{current_user_branch}")
                        house_ref.update({ "CR": f"{user_by_id.S_ID}"})
                    else:
                        years_ref = firebase_db.reference(f"/Gandhi_Institute_For_Technology/years/{current_user_semester}/{current_user_branch}")                    
                        years_ref.update({ "CR": f"{user_by_id.S_ID}"})

                    flash(f"Successfully appointed {user_by_id.StudentName} as CR.", "success")
                except Exception as e:
                    db.session.rollback()
                    flash(f"Error appointing CR for {user_by_id.StudentName}: {str(e)}", "danger")
            else:
                flash(f"Student with ID {id} not found.", "error")   

            return redirect(url_for('show_students'))

        elif request.method == "GET":
            return "use post method"
    
    @app.route('/back_for_admin')
    def back_for_admin():
        if 'user' in session:
            if session['user'] == "admin":
                return redirect(url_for('admin'))
            else:
                return redirect(url_for('login'))
        return redirect(url_for('login'))
    
    @app.route('/show_teachers', methods=["GET", "POST"])
    def show_teachers():
        if 'user' in session:
            if session.get('user') != "admin":
                return redirect(url_for('login'))
            
            all_teacher = db.session.query(Teacher).filter(Teacher.TeacherName != "ADMIN").all()
            test = []

            for s in all_teacher:
                test.append({
                    "Name": s.TeacherName,
                    "ID": s.T_ID,                        
                    "Initials": s.Initials
                })
                        
            return render_template('show_teacher.html', user=session["user"], final_data=test)
        return redirect(url_for('login'))
    
    @app.route('/subject', methods=["GET", "POST"])
    def show_selected_subject():
        if 'user' in session:
            if session['user'] == "student":
                group_name = request.form.get("subject_name")
                branch = request.form.get("subject_branch")
                semester = request.form.get("subject_semester")
                subject = request.form.get("subject_subject")
                cr_name = request.form.get("cr_name")
                cr_id = int(request.form.get("cr_id"))
                teacher_name = request.form.get("teacher_name")
                gtype = "house" if semester == "1st" or semester == "2nd" else "years"

                cr_id_link = f"/Gandhi_Institute_For_Technology/{gtype}/{semester}/{branch}/CR"
                ref = firebase_db.reference(cr_id_link)
                cr_id_from_fire = int(ref.get())

                can_upload = True if cr_id_from_fire == session["id"] else False        

                cr = Student.query.filter_by(S_ID=cr_id).first()
                cr_data = {
                    "name":cr.StudentName,
                    "role":cr.Role,
                    "id": cr.Initials + str(cr_id)
                }

                total_files = []
                main_par = "/Gandhi_Institute_For_Technology"
                construct_child_par = main_par + f"/{gtype}/{semester}/{branch}/{subject}/content"
                ref = firebase_db.reference(construct_child_par)
                c = ref.get()

                if c != None:
                    for keys in c.keys():
                        new_construct_child_par = construct_child_par + f"/{keys}"
                        r1 = firebase_db.reference(new_construct_child_par)
                        total_files.append(r1.get())


                return render_template("show_selected_subject.html", total_files=total_files, can_upload=can_upload, cr_data=cr_data, teacher_name=teacher_name, group_name=group_name, subject=subject, semester=semester,branch=branch)
            else:
                return redirect(url_for(login))
        else:
            return redirect(url_for(login))
    
    @app.route('/upload_to_google_drive', methods=["GET", "POST"])
    def cr_upload():
        if 'user' in session:
            if session['user'] == "student" and request.method == "POST":
                SCOPES = ["https://www.googleapis.com/auth/drive"]
                SERVICE_ACCOUNT_FILE = "service_account.json"
                PARENT_FOLDER_ID = config["drive"]["parent_folder_id"]
                creds = authenticate(SERVICE_ACCOUNT_FILE, SCOPES)

                groupname1 = request.form.get('groupname')
                branchCR = request.form.get('branch').strip()
                semesterCR = request.form.get('semester').strip()
                subjectCR = request.form.get('subject')

                try:
                    file_to_upload = request.files.get('file')
                except Exception as ex:
                    print("file error", ex)
                    file_to_upload = request.files.get('file')

                service = build('drive', 'v3', credentials=creds)

                now = datetime.now()
                timestamp_str = now.strftime("%Y-%m-%d %H-%M-%S")
                final_file_name = f"{file_to_upload.filename}_{timestamp_str}_{groupname1}_{subjectCR}"

                if subjectCR != "" or semesterCR != "" or branchCR != "" or subjectCR != None or semesterCR != None or branchCR != None:

                    file_metadata = {
                        'name':  final_file_name,
                        'parents': [PARENT_FOLDER_ID]
                    }
                    
                    try:
                        media = io.BytesIO(file_to_upload.read())
                        media_body = MediaIoBaseUpload(media, mimetype=file_to_upload.content_type, resumable=True)

                        f = service.files().create(
                            body=file_metadata,
                            media_body=media_body,
                            fields='id'
                        ).execute()

                        file_id_to_push = f.get('id')
                        content_link = f"https://drive.google.com/file/d/{file_id_to_push}/view?usp=sharing"

                        g1typeCR = "house" if semesterCR == "1st" or semesterCR == "2nd" else "years"
                        print(f"{g1typeCR}1 type for {semesterCR} -- {branchCR} -- {subjectCR}")
                        ref = firebase_db.reference(f"/Gandhi_Institute_For_Technology/{g1typeCR}/{semesterCR}/{branchCR}/{subjectCR}/content")
                        print(f"/Gandhi_Institute_For_Technology/{g1typeCR}/{semesterCR}/{branchCR}/{subjectCR}/content")
                        new_content_ref = ref.push()
                        new_content_ref.set({
                            "fileid": file_id_to_push,
                            "link": content_link,
                            "uploaded_on": timestamp_str,
                            "by": session["name"],
                            "group": groupname1,
                            "file_name": final_file_name,
                            "branch": branchCR,
                            "semester": semesterCR,
                            "subject": subjectCR                    
                        })
                        

                        flash('File uploaded successfully!', 'success')
                        try:
                            send_mail(content_link, semesterCR, branchCR, subjectCR, session["email"], session["name"])
                        except Exception as emailEX:
                            print("Email error: ",emailEX)
                        return render_template("response_cr_upload.html")

                    except Exception as e:
                        flash(f"An error occurred: {e}", 'error')
                        return render_template("response_cr_upload.html")
                else:
                    flash(f"An error occurred when you tried to set the file name... try again", 'error')
                    return render_template("response_cr_upload.html")
            else:
                return redirect(url_for(login))
        else:
            return redirect(url_for(login))

    # utility functions
    def register_students_through_excel(file, semesters, branches):
        Error_List = []
        df = pd.read_excel(file)
        columns_from_excel = df.columns
        validators = ['StudentName', 'Initials', 'Password', 'Branch', 'Semester', 'Email']
        initials = ["S2021-", "S2022-", "S2023-", "S2024-", "S2025-", "S2026-", "S2027-", "S2028-", "S2029-"]

        for cols in columns_from_excel:
            if cols not in validators:
                return "Wrong data format"


        row_count = 0
        for _, row in df.iterrows():
            row_count += 1
            sname = row["StudentName"]
            sinitials = row["Initials"]
            spass = row["Password"]
            sbranch = row["Branch"]
            sbranchid = None
            ssemester = row["Semester"]
            ssemid = None
            semail = row["Email"]
            can_proceed_row = True

            if(pd.isnull(sname) or str(sname).strip("") == "" or pd.isnull(sinitials) or str(sinitials).strip("") == "" or pd.isnull(spass) or str(spass).strip("") == "" or pd.isnull(sbranch) or str(sbranch).strip("") == "" or pd.isnull(ssemester) or str(ssemester).strip("") == "" or pd.isnull(semail) or str(semail).strip("") == ""):
                Error_List.append(f"For row-{row_count} value cannot be blank")
                can_proceed_row = False

            if sinitials not in initials:
                Error_List.append(f"Error in row {row_count} for '{sname}': Value mismatch in 'Initials' column: '{sinitials}' not found.")
                can_proceed_row = False
            elif "@" not in semail:
                Error_List.append(f"Error in row {row_count} for '{sname}': Invalid format for email address.")
                can_proceed_row = False
            else:
                semester_found = False
                for s in semesters:
                    if s["SemesterName"].lower() == ssemester.lower():
                        ssemid = s["SemesterID"]
                        branch_found = False
                        for b in branches:
                            if b["BranchName"].lower() == sbranch.lower() and b["SemesterID"] == ssemid:
                                sbranchid = b["BranchID"]
                                branch_found = True
                                break
                        if not branch_found:
                            Error_List.append(f"Error in row {row_count} for '{sname}': Value mismatch in 'Branch' column: '{sbranch}' not found.")
                            can_proceed_row = False
                        semester_found = True
                        break
                if not semester_found:
                    Error_List.append(f"Error in row {row_count} for '{sname}': Value mismatch in 'Semester' column: '{ssemester}' not found.")
                    can_proceed_row = False
            
            sbranch = sbranch.lower()
            ssemester = ssemester.lower()
            sinitials = sinitials.capitalize()
            if can_proceed_row:
                existing_student = Student.query.filter_by(
                StudentName=row["StudentName"],
                Initials=sinitials,
                Branch=sbranch,
                Semester=ssemester
                ).first()
                
                if existing_student:
                    Error_List.append(f"Error in row {row_count} for '{sname}': User already exists")
                else:
                    new_student = Student(
                            StudentName=sname,
                            Initials=sinitials,
                            Branch=sbranch,
                            Semester=ssemester,
                            Password=spass,
                            Email=semail
                        )
                    db.session.add(new_student)
                    db.session.commit()

        if Error_List:
            return Error_List
        else:
            return "done"


    def show_commom_group_to_student(branch, semester, group_name):
        common_ref = firebase_db.reference(f"/Gandhi_Institute_For_Technology/common/{group_name}")
        d = common_ref.get()
        teachers = []
        content_filename = []

        for v in d.keys():
            if(v != 'data' and v != 'content'):
                teachers.append(d[v])
            elif(v == 'content'):
                for keys in d[v].keys():
                    content_filename.append(d[v][keys])
        print(content_filename)
        return teachers, content_filename
    

    def show_individual_group_to_student(branch, semester):
        subjects = []
        cr_id = ""
        if(semester == "1st" or semester == "2nd"):
            house_ref = firebase_db.reference(f"/Gandhi_Institute_For_Technology/house/{semester}/{branch}")
            h = house_ref.get()            
            for subs in h.keys():
                if(subs != "CR" and subs != "data"):
                    subjects.append(h[subs])
                elif subs == "CR":
                    cr_id = h[subs]
        else:
            year_ref = firebase_db.reference(f"/Gandhi_Institute_For_Technology/years/{semester}/{branch}")
            y = year_ref.get()
            for subs in y.keys():
                if(subs!="CR" and subs!="data"):
                    subjects.append(y[subs])
                elif subs == "CR":
                    cr_id = y[subs]

        return subjects, cr_id

    def group_by_student_branch_and_semester(data):
        from collections import defaultdict
        grouped_data = defaultdict(list)
        for item in data:
            for key, value in item.items():
                grouped_data[key].extend(value)

        ret_data = dict(grouped_data)        
        return ret_data



    # CHATBOT - ADITYA
    def ensure_nltk_resources():
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            print("Downloading NLTK 'punkt' resource...")
            nltk.download('punkt')

        try:
            nltk.data.find('corpora/stopwords')
        except LookupError:
            print("Downloading NLTK 'stopwords' resource...")
            nltk.download('stopwords')

    
    from sumy.parsers.plaintext import PlaintextParser
    from sumy.nlp.tokenizers import Tokenizer
    from sumy.summarizers.lsa import LsaSummarizer

    app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024

    UPLOAD_FOLDER = 'uploads'
    SUMMARY_FOLDER = 'summaries'
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(SUMMARY_FOLDER, exist_ok=True)
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    app.config['SUMMARY_FOLDER'] = SUMMARY_FOLDER

    @app.route('/chatbot')
    def chatbot_ui():
        if 'user' in session:
            if session['user'] == "student":
                return render_template('chatbot.html')
        else:
            return redirect(url_for(login))
    
    @app.route('/get_subjects')
    def get_subjects():
        session_b = session["branch"]
        session_s = session["semester"]
        session_id = session["id"]

        user = Student.query.filter_by(S_ID=session_id).first()
        SQl_b = user.Branch
        SQL_s = user.Semester
        type_of_user = "house" if SQL_s == "1st" or SQL_s == "2nd" else "years"

        construct_firebase_url = f"/Gandhi_Institute_For_Technology/{type_of_user}/{SQL_s}/{SQl_b}"
        ref = firebase_db.reference(construct_firebase_url)
        parent_dict = ref.get()
        subject_map = {}
        mock_data = {}
        all_data = Links.query.filter_by(Branch=SQl_b, Semester=SQL_s).all()

        for item in all_data:
            clean_subject = str(item.Subject).strip().replace(" ", "").lower()
            subject_map[clean_subject] = {
                "videoLink": item.Link if item.Link != None and item.Link != "" else "#",
                "notes": item.Comment if item.Comment != None and item.Comment != "" else "no notes added"
            }
        
        t = []
        if parent_dict is not None:
            for keys2 in parent_dict.keys():
                if keys2 != "CR" and keys2 != "data":
                    keys1 = str(keys2).strip().replace(" ", "").lower()
                    for k in subject_map.keys():
                        if k == keys1:
                            t.append(keys2)
                            mock_data[keys2] = {
                                "videoLink": subject_map[k]["videoLink"],
                                "notes": subject_map[k]["notes"]
                            }
                        else:
                            continue
        else:
            mock_data = {
                "..."
            }
        return jsonify(mock_data), 200
    
    def extract_text_from_pdf(pdf_path):
        doc = fitz.open(pdf_path)
        return " ".join(page.get_text() for page in doc)

    def summarize_with_sumy(text):
        parser = PlaintextParser.from_string(text, Tokenizer("english"))
        summarizer = LsaSummarizer()
        total_words = len(text.split())
        count = 15 if total_words < 1500 else 30 if total_words < 3000 else 40
        summary_sentences = summarizer(parser.document, count)
        return "\n".join(str(sentence) for sentence in summary_sentences)

    @app.route('/upload-pdf', methods=['POST'])
    def upload_pdf():
        ensure_nltk_resources()
        if 'pdf' not in request.files:
            return jsonify({'error': 'No file part'}), 400

        file = request.files['pdf']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400

        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        try:
            text = extract_text_from_pdf(filepath)
            if not text.strip():
                return jsonify({'error': 'PDF is empty or unreadable'}), 400

            summary = summarize_with_sumy(text)

            summary_pdf_path = os.path.join(SUMMARY_FOLDER, f"summary_{filename}")
            pdf = FPDF()
            pdf.add_page()
            pdf.set_auto_page_break(auto=True, margin=15)
            font_path = "fonts/DejaVuSans.ttf"
            if not os.path.exists(font_path):
                return jsonify({'error': 'Missing font file: DejaVuSans.ttf'}), 500
            pdf.add_font("DejaVu", "", font_path, uni=True)
            pdf.set_font("DejaVu", "", 12)            
            pdf.multi_cell(0, 10, summary)
            pdf.unifontsubset = True
            pdf.output(summary_pdf_path)

            return jsonify({'download_link': f'/download-summary/{os.path.basename(summary_pdf_path)}'})
        except Exception as e:
            return jsonify({'error': f'Failed to process PDF: {str(e)}'}), 500

    # Download Summary
    @app.route('/download-summary/<filename>')
    def download_summary(filename):
        file_path = os.path.join(app.config['SUMMARY_FOLDER'], filename)
        return send_file(file_path, as_attachment=True)

    # subject summary sumy
    @app.route('/generate-summary', methods=['POST'])
    def generate_summary():
        ensure_nltk_resources()
        data = request.get_json()
        note_text = data.get('noteText', '')

        if not note_text:
            return jsonify({'summary': 'No notes provided to summarize.'})

        try:
            parser = PlaintextParser.from_string(note_text, Tokenizer("english"))
            summarizer = LsaSummarizer()
            summary_sentences = summarizer(parser.document, 5)
            summary = " ".join(str(sentence) for sentence in summary_sentences)
            return jsonify({'summary': summary})
        except Exception as e:
            print("Summary error:", e)
            return jsonify({'summary': f'Error generating summary: {str(e)}'})
        


    # HANDLES DELETION (CR AND TEACHER - ONLY FOR INDIVIDUAL GROUPS)
    @app.route('/delete_indiv', methods=["GET", "POST"])
    def delete_indiv():

        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build
        SCOPES = ['https://www.googleapis.com/auth/drive']
        SERVICE_ACCOUNT_FILE = "service_account.json"
        PARENT_FOLDER_ID = config["drive"]["parent_folder_id"]
        creds = authenticate(SERVICE_ACCOUNT_FILE, SCOPES)
        service = build('drive', 'v3', credentials=creds)

        dsubject = request.form.get('subject')
        dbranch = request.form.get('branch')
        dsem = request.form.get('semester')
        dfile = request.form.get('fileid')
        dtype = "house" if dsem == "1st" or dsem == "2nd" else "years"
        person = request.form.get("person")

        parent_url = f"/Gandhi_Institute_For_Technology/{dtype}/{dsem}/{dbranch}/{dsubject}/content"
        ref = firebase_db.reference(parent_url)
        test = ref.get()

        try:
            for t in test.keys():
                test_url = parent_url + f"/{t}"
                t1 = firebase_db.reference(test_url)
                temp_dict = t1.get()

                if temp_dict["fileid"] == dfile:
                    t1.delete()
                    service.files().delete(fileId=dfile).execute()
                    if person == "cr":
                        flash('File Deleted', 'warning')
                        return render_template("response_cr_upload.html")
                    elif person == "teacher":
                        flash('File Deleted', 'warning')
                        return render_template("return_t.html")
        except Exception as ex:
            if person == "cr":
                flash(f"An error occurred: {ex}", 'error')
                return render_template("response_cr_upload.html")
            elif person == "teacher":
                flash(f"An error occurred: {ex}", 'error')
                return render_template("return_t.html")
    
    # HANDLES DELETION OF FILES IN COMMON GROUP ONLY FOR TEACHERS
    @app.route('/common_delete', methods=["POST"])
    def common_delete():
        if 'user' in session:
            if session["user"] == "teacher" and request.method == "POST":

                from google.oauth2.service_account import Credentials
                from googleapiclient.discovery import build
                SCOPES = ['https://www.googleapis.com/auth/drive']
                SERVICE_ACCOUNT_FILE = "service_account.json"
                PARENT_FOLDER_ID = config["drive"]["parent_folder_id"]
                creds = authenticate(SERVICE_ACCOUNT_FILE, SCOPES)
                service = build('drive', 'v3', credentials=creds)

                fileid = request.form.get('fileid')
                group_from_common = request.form.get('group')
                try:
                    parent_url1 = f"/Gandhi_Institute_For_Technology/common/{group_from_common}/content"
                    ref = firebase_db.reference(parent_url1)
                    test_temp = ref.get()
                    
                    k=[]
                    for tkeys in test_temp.keys():
                        url_2 = parent_url1 + f"/{tkeys}"
                        r2 = firebase_db.reference(url_2)
                        t2 = r2.get()
                        fileid_in_firebase = t2["fileid"]

                        if fileid == fileid_in_firebase:
                            r2.delete()
                            service.files().delete(fileId=fileid).execute()
                    
                    flash("File deleted", "success")
                    return redirect(url_for('show_sections'))
                except Exception as ex:
                    flash("Unable to delete", "error")
                    print("Error in common deletion: ",ex)
                    return redirect(url_for('show_sections'))

            return redirect(url_for('login'))
        return redirect(url_for('login'))


    def send_mail(content_link, semester, branch, subject, email, name):
        destination_users = Student.query.filter_by(Branch=branch, Semester=semester).all()
        users_email = []

        for users in destination_users:
            users_email.append(users.Email)
        
        users_email = set(users_email)
        EMAIL_ADDRESS = config["mail"]["username"]
        EMAIL_PASSWORD = config["mail"]["password"]

        email_subject = "New File Uploaded"
        email_body = f"""
            A new study material for the subject *{subject}* has been uploaded by *{name}*.

            You can access the material by clicking on the following link:

            {content_link}

            Please go through the material to stay updated with the course content.

            Best regards,
            [{name}]
        """

        try:
            msg = EmailMessage()
            msg['Subject'] = email_subject
            msg['From'] = EMAIL_ADDRESS
            msg['To'] = ', '.join(users_email)
            msg.set_content(email_body)

            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
                smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
                smtp.send_message(msg)

        except Exception as insideMail:
            print(f"Error in sending mail function: {insideMail}")