import sqlite3
import bcrypt
import random

from flask import Flask
from flask import render_template
from flask import request
from flask import redirect
from flask import session
from flask import flash
from flask import send_file
from datetime import datetime
current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

app = Flask(__name__)
app.secret_key = "bank_secret_key"


# DATABASE CONNECTION
def get_db_connection():
    conn = sqlite3.connect("database/bank.db")
    conn.row_factory = sqlite3.Row
    return conn

# CREATE TABLES
def create_tables():

    conn = get_db_connection()
    cursor = conn.cursor()

    # USERS TABLE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        phone TEXT NOT NULL,
        password TEXT NOT NULL
    )
    """)

    # ACCOUNTS TABLE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS accounts(
        account_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        account_number TEXT UNIQUE NOT NULL,
        account_type TEXT NOT NULL,
        balance REAL DEFAULT 0,
        status TEXT DEFAULT 'Active',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)

    # TRANSACTIONS TABLE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions(
        transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER NOT NULL,
        transaction_type TEXT NOT NULL,
        amount REAL NOT NULL,
        description TEXT,
        balance_after REAL NOT NULL,
        transaction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(account_id) REFERENCES accounts(account_id)
    )
    """)


# =========================
# ADMIN TABLES SECTION
# =========================

# ADMIN LOGS TABLE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admin_logs (
        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
        admin_username TEXT,
        action TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

# ADMIN TABLE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admin (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password BLOB NOT NULL
    )
    """)

# CHECK IF DEFAULT ADMIN EXISTS
    cursor.execute("""
    SELECT * FROM admin
    WHERE username = 'admin'
    """)

    existing_admin = cursor.fetchone()

# CREATE DEFAULT ADMIN ONLY IF NOT EXISTS
    if not existing_admin:

        import bcrypt

        hashed_password = bcrypt.hashpw(
            "admin123".encode('utf-8'),
            bcrypt.gensalt()
        )

        cursor.execute("""
        INSERT INTO admin (username, password)
        VALUES (?, ?)
        """, ("admin", hashed_password))

    conn.commit()
    conn.close()


# HOME
@app.route('/')
def home():
    return render_template('index.html')


# ABOUT
@app.route('/about')
def about():
    return render_template('about.html')


# GET STARTED
@app.route('/get-started')
def get_started():
    return render_template('get_started.html')


# REGISTER
@app.route('/register', methods=['GET', 'POST'])
def register():

    if request.method == 'POST':

        full_name = request.form['full_name']
        email = request.form['email']
        phone = request.form['phone']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            flash("Passwords do not match")
            return redirect('/register')

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM users WHERE email=?",
            (email,)
        )

        existing_user = cursor.fetchone()

        if existing_user:
            flash("Email already exists")
            conn.close()
            return redirect('/register')

        hashed_password = bcrypt.hashpw(
            password.encode('utf-8'),
            bcrypt.gensalt()
        )

        cursor.execute("""
        INSERT INTO users
        (full_name,email,phone,password)
        VALUES(?,?,?,?)
        """,
        (
            full_name,
            email,
            phone,
            hashed_password
        ))

        conn.commit()
        conn.close()

        flash("Registration Successful")
        return redirect('/login')

    return render_template('register.html')


# LOGIN
@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM users WHERE email=?",
            (email,)
        )

        user = cursor.fetchone()

        conn.close()

        if user:

            if bcrypt.checkpw(
                password.encode('utf-8'),
                user['password']
            ):

                session['user_id'] = user['id']
                session['user_name'] = user['full_name']

                return redirect('/dashboard')

        flash("Invalid Email or Password")
        return redirect('/login')

    return render_template('login.html')


# DASHBOARD
@app.route('/dashboard')
def dashboard():

    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT COUNT(*) as total_accounts
    FROM accounts
    WHERE user_id = ?
    """,
    (session['user_id'],))

    total_accounts = cursor.fetchone()['total_accounts']

    cursor.execute("""
    SELECT SUM(balance) as total_balance
    FROM accounts
    WHERE user_id = ?
    """,
    (session['user_id'],))

    result = cursor.fetchone()

    total_balance = result['total_balance']

    if total_balance is None:
        total_balance = 0

    cursor.execute("""
    SELECT COUNT(*)
    FROM accounts
    WHERE user_id = ?
    AND account_type = 'Savings'
    """, (session['user_id'],))

    savings_accounts = cursor.fetchone()[0]


    cursor.execute("""
    SELECT COUNT(*)
    FROM accounts
    WHERE user_id = ?
    AND account_type = 'Current'
    """, (session['user_id'],))

    current_accounts = cursor.fetchone()[0]


    cursor.execute("""
    SELECT full_name
    FROM users
    WHERE id = ?
    """, (session['user_id'],))

    user = cursor.fetchone()

    name = user['full_name']
    conn.close()

    return render_template(
    'dashboard.html',
    name=name,
    total_accounts=total_accounts,
    total_balance=total_balance,
    savings_accounts=savings_accounts,
    current_accounts=current_accounts
)

    


@app.route('/profile')
def profile():

    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT * FROM users
    WHERE id = ?
    """, (session['user_id'],))

    user = cursor.fetchone()

    conn.close()

    return render_template(
        'profile.html',
        user=user
    )


#CREATE ACCOUNT
@app.route('/create-account', methods=['GET', 'POST'])
def create_account():

    if 'user_id' not in session:
        return redirect('/login')

    if request.method == 'POST':

        account_type = request.form['account_type']

        account_number = str(random.randint(1000000000, 9999999999))

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
        INSERT INTO accounts
        (user_id, account_number, account_type, balance, status)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            session['user_id'],
            account_number,
            account_type,
            0,
            'Active'
        ))

        conn.commit()
        conn.close()

        flash("Account Created Successfully")

        return redirect('/accounts')

    return render_template('create_account.html')


#ACCOUNTS
@app.route('/accounts')
def accounts():

    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT * FROM accounts
    WHERE user_id = ?
    """,
    (session['user_id'],))

    accounts = cursor.fetchall()

    conn.close()

    return render_template(
        'accounts.html',
        accounts=accounts
    )


# LOGOUT
@app.route('/logout')
def logout():

    session.clear()

    flash("Logged Out Successfully")

    return redirect('/login')


#deposit
@app.route('/deposit', methods=['GET', 'POST'])
def deposit():

    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()

    # GET ALL ACCOUNTS FOR DROPDOWN
    cursor.execute("""
    SELECT * FROM accounts
    WHERE user_id = ?
    """, (session['user_id'],))

    accounts = cursor.fetchall()

    # IF FORM SUBMITTED
    if request.method == 'POST':

        account_id = request.form['account_id']
        amount = float(request.form['amount'])

        if amount <= 0:
            flash("Please enter a valid amount")
            conn.close()
            return redirect('/deposit')
        amount = float(request.form['amount'])
        description = request.form['description']

        # GET CURRENT BALANCE
        cursor.execute("""
        SELECT * FROM accounts
        WHERE account_id = ?
        """, (account_id,))

        account = cursor.fetchone()

        new_balance = account['balance'] + amount

        # UPDATE ACCOUNT BALANCE
        cursor.execute("""
        UPDATE accounts
        SET balance = ?
        WHERE account_id = ?
        """, (new_balance, account_id))

        # INSERT TRANSACTION
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
        INSERT INTO transactions (
            account_id,
            transaction_type,
            amount,
            description,
            balance_after,
            transaction_date
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            account_id,
            'Deposit',
            amount,
            description,
            new_balance,
            current_time
        ))

        conn.commit()
        conn.close()

        flash("Deposit Successful!")
        return redirect('/accounts')

    conn.close()

    return render_template('deposit.html', accounts=accounts)


#WITHDRAW
@app.route('/withdraw', methods=['GET', 'POST'])
def withdraw():

    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()

    # GET USER ACCOUNTS
    cursor.execute("""
    SELECT * FROM accounts
    WHERE user_id = ?
    """, (session['user_id'],))

    accounts = cursor.fetchall()

    if request.method == 'POST':

        account_id = request.form['account_id']
        amount = float(request.form['amount'])

        # GET ACCOUNT
        cursor.execute("""
        SELECT * FROM accounts
        WHERE account_id = ?
        """, (account_id,))

        account = cursor.fetchone()

        # CHECK BALANCE
        if amount <= 0:
            flash("Please enter a valid amount")
            conn.close()
            return redirect('/withdraw')

        if account['balance'] < amount:
            flash("Insufficient Balance!")
            conn.close()
            return redirect('/withdraw')

        new_balance = account['balance'] - amount

        # UPDATE BALANCE
        cursor.execute("""
        UPDATE accounts
        SET balance = ?
        WHERE account_id = ?
        """, (new_balance, account_id))

        # INSERT TRANSACTION
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
        INSERT INTO transactions (
            account_id,
            transaction_type,
            amount,
            description,
            balance_after,
            transaction_date          
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            account_id,
            'Withdraw',
            amount,
            'Money Withdrawn',
            new_balance,
            current_time
        ))

        conn.commit()
        conn.close()

        flash("Withdrawal Successful!")
        return redirect('/accounts')

    conn.close()

    return render_template('withdraw.html', accounts=accounts)


#TRANSTER
@app.route('/transfer', methods=['GET', 'POST'])
def transfer():

    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()

    # GET USER ACCOUNTS (for dropdown)
    cursor.execute("""
    SELECT * FROM accounts
    WHERE user_id = ?
    """, (session['user_id'],))

    accounts = cursor.fetchall()

    if request.method == 'POST':

        from_account_id = request.form['from_account']
        to_account_number = request.form['to_account_number']
        amount = float(request.form['amount'])

        # GET SENDER ACCOUNT
        cursor.execute("""
        SELECT * FROM accounts
        WHERE account_id = ?
        """, (from_account_id,))

        sender = cursor.fetchone()

        if not sender:
            flash("Sender Account Not Found!")
            conn.close()
            return redirect('/transfer')

        if amount <= 0:
             flash("Please enter a valid amount")
             conn.close()
             return redirect('/transfer')

        # CHECK BALANCE
        if sender['balance'] < amount:
            flash("Insufficient Balance!")
            conn.close()
            return redirect('/transfer')

        # GET RECEIVER ACCOUNT
        cursor.execute("""
        SELECT * FROM accounts
        WHERE account_number = ?
        """, (to_account_number,))

        receiver = cursor.fetchone()

        if not receiver:
            flash("Receiver Account Not Found!")
            conn.close()
            return redirect('/transfer')

        # UPDATE BALANCES
        sender_new_balance = sender['balance'] - amount
        receiver_new_balance = receiver['balance'] + amount

        cursor.execute("""
        UPDATE accounts
        SET balance = ?
        WHERE account_id = ?
        """, (sender_new_balance, from_account_id))

        cursor.execute("""
        UPDATE accounts
        SET balance = ?
        WHERE account_id = ?
        """, (receiver_new_balance, receiver['account_id']))

        # TRANSACTION 1 (DEBIT)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
        INSERT INTO transactions (
            account_id,
            transaction_type,
            amount,
            description,
            balance_after,
            transaction_date
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            from_account_id,
            'Transfer Debit',
            amount,
            f'Transferred to {to_account_number}',
            sender_new_balance,
            current_time
        ))

        # TRANSACTION 2 (CREDIT)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
        INSERT INTO transactions (
            account_id,
            transaction_type,
            amount,
            description,
            balance_after,
            transaction_date
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            receiver['account_id'],
            'Transfer Credit',
            amount,
            f'Received from {sender["account_number"]}',
            receiver_new_balance,
            current_time
        ))

        conn.commit()
        conn.close()

        flash("Transfer Successful!")
        return redirect('/accounts')

    conn.close()

    return render_template('transfer.html', accounts=accounts)


#DOWNLOAD AS TXT  STATEMENT
from flask import Response

@app.route('/download-txt')
def download_txt():

    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT t.*
    FROM transactions t
    JOIN accounts a
    ON t.account_id = a.account_id
    WHERE a.user_id = ?
    ORDER BY transaction_date DESC
    """, (session['user_id'],))

    transactions = cursor.fetchall()

    conn.close()

    statement = "SECURE BANK STATEMENT\n\n"

    for t in transactions:
        statement += (
            f"{t['transaction_date']} | "
            f"{t['transaction_type']} | "
            f"₹{t['amount']}\n"
        )

    return Response(
        statement,
        mimetype="text/plain",
        headers={
            "Content-Disposition":
            "attachment;filename=statement.txt"
        }
    )

#DOWNLOAD AS .docx
from docx import Document

@app.route('/download-docx')
def download_docx():

    document = Document()

    document.add_heading(
        'Secure Bank Statement',
        level=1
    )

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT t.*
    FROM transactions t
    JOIN accounts a
    ON t.account_id = a.account_id
    WHERE a.user_id = ?
    """, (session['user_id'],))

    transactions = cursor.fetchall()

    conn.close()

    for t in transactions:

        document.add_paragraph(
            f"{t['transaction_date']} | "
            f"{t['transaction_type']} | "
            f"₹{t['amount']}"
        )

    document.save("statement.docx")

    return send_file(
        "statement.docx",
        as_attachment=True
    )

#DOWNLOAD AS PDF
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

@app.route('/download-pdf')
def download_pdf():

    pdf_file = "statement.pdf"

    doc = SimpleDocTemplate(pdf_file)

    styles = getSampleStyleSheet()

    content = [
        Paragraph(
            "Secure Bank Statement",
            styles['Title']
        )
    ]

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT t.*
    FROM transactions t
    JOIN accounts a
    ON t.account_id = a.account_id
    WHERE a.user_id = ?
    """, (session['user_id'],))

    transactions = cursor.fetchall()

    conn.close()

    for t in transactions:

        content.append(
            Paragraph(
                f"{t['transaction_date']} | "
                f"{t['transaction_type']} | "
                f"₹{t['amount']}",
                styles['Normal']
            )
        )

    doc.build(content)

    return send_file(
        pdf_file,
        as_attachment=True
    )


#TRANSACTIONS
@app.route('/transactions')
def transactions():

    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get all accounts of user
    cursor.execute("""
    SELECT account_id FROM accounts
    WHERE user_id = ?
    """, (session['user_id'],))

    user_accounts = cursor.fetchall()

    account_ids = [acc['account_id'] for acc in user_accounts]

    if len(account_ids) == 0:
        return render_template('transactions.html', transactions=[])

    # Get transactions for those accounts
    query = f"""
    SELECT * FROM transactions
    WHERE account_id IN ({','.join(['?']*len(account_ids))})
    ORDER BY transaction_date DESC
    """

    cursor.execute(query, account_ids)

    transactions = cursor.fetchall()

    conn.close()

    return render_template('transactions.html', transactions=transactions)

#MANAGE CUSTOMERS
@app.route('/manage-customers')
def manage_customers():

    print("MANAGE CUSTOMERS OPENED")

    if 'admin' not in session:
        return redirect('/admin-login')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT id, full_name, email, phone
    FROM users
    ORDER BY id DESC
    """)

    customers = cursor.fetchall()

    print(customers)

    conn.close()

    return render_template(
        'manage_customers.html',
        customers=customers
    )

# CUSTOMER DETAILS
@app.route('/customer/<int:user_id>')
def customer_details(user_id):

    if 'admin' not in session:
        return redirect('/admin-login')

    conn = get_db_connection()
    cursor = conn.cursor()

    # CUSTOMER INFO
    cursor.execute("""
    SELECT *
    FROM users
    WHERE id = ?
    """, (user_id,))

    customer = cursor.fetchone()

    # CUSTOMER ACCOUNTS
    cursor.execute("""
    SELECT *
    FROM accounts
    WHERE user_id = ?
    """, (user_id,))

    accounts = cursor.fetchall()

    # TOTAL BALANCE
    cursor.execute("""
    SELECT SUM(balance)
    FROM accounts
    WHERE user_id = ?
    """, (user_id,))

    total_balance = cursor.fetchone()[0]

    if total_balance is None:
        total_balance = 0

    conn.close()

    return render_template(
        'customer_details.html',
        customer=customer,
        accounts=accounts,
        total_balance=total_balance
    )

# MANAGE TRANSACTIONS
@app.route('/manage-transactions')
def manage_transactions():

    if 'admin' not in session:
        return redirect('/admin-login')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT *
    FROM transactions
    ORDER BY transaction_id DESC
    """)

    transactions = cursor.fetchall()

    conn.close()

    return render_template(
        'manage_transactions.html',
        transactions=transactions
    )


# REPORTS
@app.route('/reports')
def reports():

    if 'admin' not in session:
        return redirect('/admin-login')

    conn = get_db_connection()
    cursor = conn.cursor()

    # Total Customers
    cursor.execute("SELECT COUNT(*) FROM users")
    total_customers = cursor.fetchone()[0]

    # Total Accounts
    cursor.execute("SELECT COUNT(*) FROM accounts")
    total_accounts = cursor.fetchone()[0]

    # Total Transactions
    cursor.execute("SELECT COUNT(*) FROM transactions")
    total_transactions = cursor.fetchone()[0]

    # Total Deposits
    cursor.execute("""
    SELECT SUM(amount)
    FROM transactions
    WHERE transaction_type='Deposit'
    """)
    total_deposits = cursor.fetchone()[0] or 0

    # Total Withdrawals
    cursor.execute("""
    SELECT SUM(amount)
    FROM transactions
    WHERE transaction_type='Withdraw'
    """)
    total_withdrawals = cursor.fetchone()[0] or 0

    # Total Transfers
    cursor.execute("""
    SELECT SUM(amount)
    FROM transactions
    WHERE transaction_type='Transfer'
    """)
    total_transfers = cursor.fetchone()[0] or 0

    conn.close()

    return render_template(
        'reports.html',
        total_customers=total_customers,
        total_accounts=total_accounts,
        total_transactions=total_transactions,
        total_deposits=total_deposits,
        total_withdrawals=total_withdrawals,
        total_transfers=total_transfers
    )

# ADMIN LOGS
@app.route('/admin-logs')
def admin_logs():

    if 'admin' not in session:
        return redirect('/admin-login')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT *
    FROM admin_logs
    ORDER BY log_id DESC
    """)

    logs = cursor.fetchall()

    conn.close()

    return render_template(
        'admin_logs.html',
        logs=logs
    )

#ADMIN DASHBOARD
# ADMIN DASHBOARD

@app.route('/admin-dashboard')
def admin_dashboard():


    if 'admin' not in session:
        return redirect('/admin-login')

    conn = get_db_connection()
    cursor = conn.cursor()

    # TOTAL CUSTOMERS
    cursor.execute("SELECT COUNT(*) FROM users")
    total_customers = cursor.fetchone()[0]

    # TOTAL ACCOUNTS
    cursor.execute("SELECT COUNT(*) FROM accounts")
    total_accounts = cursor.fetchone()[0]

    # TOTAL TRANSACTIONS
    cursor.execute("SELECT COUNT(*) FROM transactions")
    total_transactions = cursor.fetchone()[0]

    # TOTAL DEPOSITS
    cursor.execute("""
    SELECT SUM(amount)
    FROM transactions
    WHERE transaction_type='Deposit'
    """)
    total_deposits = cursor.fetchone()[0] or 0

    # TOTAL WITHDRAWALS
    cursor.execute("""
    SELECT SUM(amount)
    FROM transactions
    WHERE transaction_type='Withdraw'
    """)
    total_withdrawals = cursor.fetchone()[0] or 0

    # ACCOUNT TYPES
    cursor.execute("""
    SELECT COUNT(*)
    FROM accounts
    WHERE account_type='Savings'
    """)
    savings_accounts = cursor.fetchone()[0]

    cursor.execute("""
    SELECT COUNT(*)
    FROM accounts
    WHERE account_type='Current'
    """)
    current_accounts = cursor.fetchone()[0]

    cursor.execute("""
    SELECT COUNT(*)
    FROM accounts
    WHERE account_type='Fixed Deposit'
    """)
    fd_accounts = cursor.fetchone()[0]

    # ACCOUNT STATUS
    cursor.execute("""
    SELECT COUNT(*)
    FROM accounts
    WHERE status='Active'
    """)
    active_accounts = cursor.fetchone()[0]

    cursor.execute("""
    SELECT COUNT(*)
    FROM accounts
    WHERE status!='Active'
    """)
    inactive_accounts = cursor.fetchone()[0]

    cursor.execute("""
    SELECT AVG(balance)
    FROM accounts
    """)

    average_balance = cursor.fetchone()[0]

    if average_balance is None:
        average_balance = 0

    average_balance = round(average_balance, 2)

    conn.close()

    return render_template(
        'admin_dashboard.html',
        total_customers=total_customers,
        total_accounts=total_accounts,
        total_transactions=total_transactions,
        total_deposits=total_deposits,
        total_withdrawals=total_withdrawals,
        savings_accounts=savings_accounts,
        current_accounts=current_accounts,
        fd_accounts=fd_accounts,
        active_accounts=active_accounts,
        inactive_accounts=inactive_accounts,
        average_balance=average_balance
    )

#ADMIN LOGIN
@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':

        username = request.form['username']
        password = request.form['password']

        cursor.execute("""
        SELECT * FROM admin
        WHERE username = ?
        """, (username,))

        admin = cursor.fetchone()

        print("ADMIN FOUND:", admin)

        if admin:

            stored_password = admin['password']

            if isinstance(stored_password, str):
                stored_password = stored_password.encode('utf-8')

            if bcrypt.checkpw(password.encode('utf-8'), stored_password):

                session['admin'] = admin['username']

                cursor.execute("""
                INSERT INTO admin_logs (admin_username, action)
                VALUES (?, ?)
                """, (admin['username'], 'Logged In'))

                conn.commit()
                conn.close()

                print("LOGIN SUCCESS")

                return redirect('/admin-dashboard')

            else:
                print("WRONG PASSWORD")

        else:
            print("ADMIN NOT FOUND")

        print("INPUT PASSWORD:", password)
        print("DB PASSWORD:", admin['password'])
        print("TYPE:", type(admin['password']))

        conn.close()
        flash("Invalid Admin Credentials")
        return redirect('/admin-login')

    conn.close()
    return render_template('admin_login.html')


# ADMIN LOGOUT
@app.route('/admin-logout')
def admin_logout():

    admin_user = session.get('admin')

    if admin_user:

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
        INSERT INTO admin_logs (admin_username, action)
        VALUES (?, ?)
        """, (admin_user, 'Logged Out'))

        conn.commit()
        conn.close()

    session.clear()
    return redirect('/admin-login')

#PASSWORD CHANGE
@app.route('/change-password', methods=['GET', 'POST'])
def change_password():

    if 'user_id' not in session:
        return redirect('/login')

    if request.method == 'POST':

        old_password = request.form['old_password']
        new_password = request.form['new_password']

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],))
        user = cursor.fetchone()

        if user and bcrypt.checkpw(old_password.encode(), user['password']):

            hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt())

            cursor.execute("""
            UPDATE users SET password = ? WHERE id = ?
            """, (hashed, session['user_id']))

            conn.commit()
            conn.close()

            return "Password Updated Successfully"

        return "Incorrect Old Password"

    return render_template('change_password.html')


#ACCOUNT FREEZ/UNFREEZ
@app.route('/toggle-account/<int:account_id>')
def toggle_account(account_id):

    if 'admin' not in session:
        return redirect('/admin-login')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT status FROM accounts WHERE account_id = ?", (account_id,))
    acc = cursor.fetchone()

    new_status = 'Frozen' if acc['status'] == 'Active' else 'Active'

    cursor.execute("""
    UPDATE accounts SET status = ? WHERE account_id = ?
    """, (new_status, account_id))

    conn.commit()
    conn.close()

    return redirect('/admin-dashboard')

#BANK STATEMENT
@app.route('/statement/<int:account_id>')
def statement(account_id):

    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT * FROM transactions
    WHERE account_id = ?
    ORDER BY transaction_date DESC
    """, (account_id,))

    data = cursor.fetchall()
    conn.close()

    return render_template('statement.html', transactions=data)


#CHECK ADMIN
@app.route('/check-admin')
def check_admin():

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM admin")
    admins = cursor.fetchall()

    conn.close()

    result = []

    for admin in admins:
        result.append(dict(admin))

    return str(result)


#CREATE ADMIN
@app.route('/create-admin')
def create_admin():

    import bcrypt

    conn = get_db_connection()
    cursor = conn.cursor()

    hashed_password = bcrypt.hashpw(
        "admin123".encode('utf-8'),
        bcrypt.gensalt()
    )

    cursor.execute("""
    INSERT INTO admin (username, password)
    VALUES (?, ?)
    """, ("admin", hashed_password))

    conn.commit()
    conn.close()

    return "Admin Created Successfully!"


#DATABASE PATH
@app.route('/db-path')
def db_path():
    import os
    return os.path.abspath('bank.db')

#ADMIN COUNT
@app.route('/admin-count')
def admin_count():

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM admin")
    count = cursor.fetchone()[0]

    conn.close()

    return f"Admin Count = {count}"



if __name__ == '__main__':
    app.run(debug=True)