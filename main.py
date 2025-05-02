import sqlite3
from flask import Flask, render_template, redirect, request, make_response, url_for, flash, send_file, session
from io import BytesIO
from werkzeug.utils import secure_filename
import hashlib
import logging
from setup import start_db
from check import generate_token, check_token


UPLOAD_FOLDER = '/home/poisoniv/Code/COP4521/Project1/files'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}

app = Flask(__name__)
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


logging.basicConfig(level=logging.DEBUG)
user = ['']


@app.route('/')
def front_page():
    return render_template('Login.html')


@app.route('/login', methods=['POST', 'GET'])
def login():
    if request.method == 'POST':
        con = sqlite3.connect('database.db')
        try:
            WorkID = request.form['WorkID']
            Password = request.form['Password']

            hashed_password = hashlib.sha256(
                Password.encode()).hexdigest()  # Correct hashing method

            cur = con.cursor()

            # Fetch the user with the provided WorkID
            cur.execute("SELECT * FROM Users WHERE WORKID = ? AND Password = ?",
                        (WorkID, hashed_password))
            rows = cur.fetchall()
            if len(rows) == 0:
                return render_template("NoMatchingUser.html")

            token = generate_token(WorkID)
            user[0] = rows[0][0]

            # Check if the user is Admin, Manager, or User
            if WorkID[0] == 'A':
                response = make_response(redirect("/AdminMainPage"))
                response.set_cookie('AuthToken', token)
            elif WorkID[0] == 'M':
                response = make_response(redirect("/ManagerMainPage"))
                response.set_cookie('AuthToken', token)
            elif WorkID[0] == 'U':
                response = make_response(redirect("/UserMainPage"))
                response.set_cookie('AuthToken', token)

            return response

        except sqlite3.Error as e:
            logging.error(f"Database Error: {e}")
            return render_template("Error.html")
        except Exception as e:
            logging.error(f"Exception Error: {e}")
            return render_template("Error.html")
        except:
            return redirect("/")
        finally:
            con.close()


@app.route('/signup', methods=['POST', 'GET'])
def signup():
    return render_template('SignUp.html')


@app.route('/signupvalid', methods=['POST', 'GET'])
def signupvalid():
    if request.method == 'POST':
        con = sqlite3.connect('database.db')
        try:
            firstName = request.form['First']
            lastName = request.form['Last']
            WorkID = request.form['WorkID']
            password = request.form['Password']
            confirm_pass = request.form['ConfirmPassword']
            # Check if the user is Admin, Manager, or User
            if WorkID[0] == 'A':
                role = 'Admin'
            elif WorkID[0] == 'M':
                role = 'Manager'
            else:
                role = 'User'
            user[0] = WorkID

            hashed_password = hashlib.sha256(password.encode()).hexdigest()

            with con:
                cur = con.cursor()

                # Check if WORKID is valid
                if not cur.execute("SELECT * FROM ValidWorkID WHERE WORKID = ?", (WorkID,)).fetchall():
                    return render_template('InvalidWorkID.html')

                # Check if WorkID is already in the database
                if cur.execute("SELECT * FROM Users WHERE WORKID = ?", (WorkID,)).fetchone():
                    return render_template('InvalidWorkID.html')

                # If password and confirm password are the same, insert the user into the database
                if password == confirm_pass:
                    cur.execute("INSERT INTO Users (WORKID, Password, First, Last) VALUES (?,?,?,?)", (
                        WorkID, hashed_password, firstName, lastName))
                    cur.execute(
                        "UPDATE Users SET Role = ? WHERE WORKID = ?", (role, WorkID))

                # Redirect regardless of the insertion status
                return redirect("/")

        except Exception as e:
            logging.error(f"Error: {e}")
            con.rollback()
            return render_template('Error.html')
        finally:
            con.close()


@app.route('/UserMainPage', methods=['POST', 'GET'])
def UserMain():
    session_token = request.cookies.get('AuthToken')

    if not check_token(session_token, user[0]):
        return render_template('TokenError.html')

    conn = sqlite3.connect('database.db')
    cur = conn.cursor()
    cur.execute("SELECT * FROM Files ORDER BY FileId DESC")
    files = cur.fetchall()

    return render_template('UserMainPage.html', Files=files)


@app.route('/ManagerMainPage', methods=['POST', 'GET'])
def ManagerMain():
    session_token = request.cookies.get('AuthToken')
    if not check_token(session_token, user[0]):
        return render_template('TokenError.html')

    conn = sqlite3.connect('database.db')
    cur = conn.cursor()
    cur.execute("SELECT * FROM Files ORDER BY FileId DESC")
    files = cur.fetchall()

    return render_template('ManagerMainPage.html', Files=files)


@app.route('/AdminMainPage', methods=['POST', 'GET'])
def AdminMain():
    session_token = request.cookies.get('AuthToken')
    if not check_token(session_token, user[0]):
        return render_template('TokenError.html')

    conn = sqlite3.connect('database.db')
    cur = conn.cursor()
    cur.execute("SELECT * FROM Users")
    users = cur.fetchall()
    cur.execute("SELECT * FROM Files ORDER BY FileId DESC")
    files = cur.fetchall()

    return render_template('AdminMainPage.html', Users=users, Files=files)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/uploadfile', methods=['POST', 'GET'])
def uploadfile():
    if request.method == 'POST':
        session_token = request.cookies.get('AuthToken')
        if not check_token(session_token, user[0]):
            return render_template('TokenError.html')

        # Check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)

        file = request.files['file']

        # If the user does not select a file, the browser submits an empty file without a filename
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            # Read the file content
            file_data = file.read()
            # Insert file data into the database
            conn = sqlite3.connect('database.db')
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO Files (FileName, FileData, WorkID) VALUES (?, ?, ?)", (filename, file_data, user[0]))
            conn.commit()
            conn.close()

        # Check if the user is Admin, Manager, or User
        if user[0][0] == 'A':
            return redirect(url_for('AdminMain'))
        elif user[0][0] == 'M':
            return redirect(url_for('ManagerMain'))
    return render_template('UploadFile.html')


@app.route('/download/<int:file_id>')
def downloadfile(file_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Files WHERE FileId=?", (file_id,))
    file = cursor.fetchone()
    return send_file(BytesIO(file[2]), download_name=file[1], as_attachment=True)


@app.route('/deletefile/<int:file_id>')
def deletefile(file_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Files WHERE FileId=?", (file_id,))
    conn.commit()
    conn.close()
    return redirect(request.referrer)


@app.route('/EditWorkID', methods=['POST', 'GET'])
def EditWorkID():
    if request.method == 'POST':
        session_token = request.cookies.get('AuthToken')
        if not check_token(session_token, user[0]):
            return render_template('TokenError.html')

        action = request.form.get('action')
        work_id = request.form.get('work_id')

        if action == 'add':
            add_work_id(work_id)
        elif action == 'delete':
            delete_work_id(work_id)

    # Fetch all existing WorkIDs from the database
    work_ids = fetch_work_ids()

    return render_template('EditWorkID.html', work_ids=work_ids)


def add_work_id(work_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Check if the WORKID already exists in the table
    cursor.execute("SELECT * FROM ValidWorkID WHERE WORKID=?", (work_id,))
    existing_row = cursor.fetchone()

    if not existing_row:
        # If the WORKID doesn't exist, insert it into the table
        cursor.execute(
            "INSERT INTO ValidWorkID (WORKID) VALUES (?)", (work_id,))
        conn.commit()
    else:
        return

    conn.close()


def delete_work_id(work_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Check that the WORKID isn't current user's WORKID
    if work_id == user[0]:
        return

    # Delete the specified WORKID from the table
    cursor.execute("DELETE FROM ValidWorkID WHERE WORKID=?", (work_id,))
    conn.commit()

    conn.close()


def fetch_work_ids():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Fetch all existing WorkIDs from the database
    cursor.execute("SELECT WORKID FROM ValidWorkID")
    work_ids = [row[0] for row in cursor.fetchall()]

    conn.close()

    return work_ids


@app.route('/DeleteUser', methods=['POST', 'GET'])
def DeleteUser():
    if request.method == 'POST':
        session_token = request.cookies.get('AuthToken')
        if not check_token(session_token, user[0]):
            return render_template('TokenError.html')

        work_id = request.form.get('work_id')
        delete_user(work_id)
        # Redirect to the main page after deletion
        return redirect(url_for('AdminMain'))

    # Fetch all user names from the Users table
    users = fetch_user_names()

    return render_template('DeleteUser.html', users=users)


def fetch_user_names():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Fetch all user names from the Users table
    cursor.execute("SELECT WORKID, First, Last FROM Users")
    users = cursor.fetchall()

    conn.close()

    return users


def delete_user(work_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Delete the user from the Users table
    cursor.execute("DELETE FROM Users WHERE WORKID=?", (work_id,))
    conn.commit()

    conn.close()


@app.route("/search", methods=['POST', 'GET'])
def searched():
    if request.method == "POST":
        conn = sqlite3.connect('database.db')
        try:
            searched = request.form["searched"]
            cur = conn.cursor()
            query = """
                SELECT * FROM Files
                WHERE FileID LIKE ?
                OR FileName LIKE ? COLLATE NOCASE
                OR WorkID LIKE ?
                ORDER BY FileID DESC"""

            cur.execute(query, ('%' + searched + '%', '%' +
                        searched + '%', '%' + searched + '%'))

            files = cur.fetchall()

            # Check if the user is Admin, Manager, or User
            if user[0][0] == 'A':
                return render_template('AdminMainPage.html', Files=files)
            elif user[0][0] == 'M':
                return render_template('ManagerMainPage.html', Files=files)
            elif user[0][0] == 'U':
                return render_template('UserMainPage.html', Files=files)

        except:
            conn.rollback()
            return render_template('Error.html')
        finally:
            conn.close()


if __name__ == "__main__":
    # Start the database
    start_db()
    app.run(debug=True)
