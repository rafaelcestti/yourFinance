from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
    get_flashed_messages,
)
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import (
    GUEST_ACCOUNT_ID,
    loginRequired,
    usd,
    checkGuest,
    getUserByID,
    getUserAccounts,
    getAccount,
    getUserAccountsID,
    getTransaction,
    getAccountTransactions,
    getAccountsTransactions,
    getMonthTotals,
    getTypeTotals,
    isBlank,
    getUser,
    isFloat,
    shortDate,
    balanceAtDate,
)
from models import db, User, Account, Transaction

# Configure application
app = Flask(__name__)

# Custom filters
app.jinja_env.filters["usd"] = usd
app.jinja_env.filters["shortDate"] = shortDate

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# configure the SQLite database
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///project.db"
# initialize the app with the extension
db.init_app(app)

# create SQL tables
with app.app_context():
    db.create_all()


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@loginRequired
def index():
    userID = session["user_id"]

    # Get account information
    accounts = getUserAccounts(userID)
    checkingTotal = getTypeTotals(accounts, "Checking")
    savingsTotal = getTypeTotals(accounts, "Savings")

    # Get transaction information
    userAccountsID = getUserAccountsID(userID)
    allTransactions = getAccountsTransactions(userAccountsID)

    monthTotals = getMonthTotals(userAccountsID)

    # Only show latest transactions
    transactions = []
    counter = 0
    for transaction in allTransactions:
        if counter < 5:
            transactions.append(transaction)
            counter += 1

    return render_template(
        "home.html",
        accounts=accounts,
        checkingTotal=checkingTotal,
        savingsTotal=savingsTotal,
        transactions=transactions,
        monthTotals=monthTotals,
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    # Clear user ID if user is logged in
    try:
        if session["user_id"]:
            session.clear()
    except:
        pass

    # Check if animation has been loaded for user
    try:
        if session["animationLoaded"]:
            animationLoaded = session["animationLoaded"]
    except:
        animationLoaded = False

    if request.method == "POST":
        checkGuestLogin = request.form.get("guestForm")
        if checkGuestLogin == "GUEST_LOGIN":
            user = getUserByID(GUEST_ACCOUNT_ID)
            if isBlank(user):
                flash("Guest does not exist", "error")
                return redirect("/login")
            session["user_id"] = user.id
            return redirect("/")

        # Query database for username
        username = request.form.get("username")
        password = request.form.get("password")

        # Ensure inputs are submitted
        if isBlank(username):
            flash("Must provide username", "error")
            return redirect("/login")
        if isBlank(password):
            flash("Must provide password", "error")
            return redirect("/login")
        
        # Ensure user exists
        user = getUser(username)
        if isBlank(user):
            flash("User does not exist", "error")
            return redirect("/login")

        # Ensure username exists and password is correct
        if not check_password_hash(user.hash, password):
            flash("Invalid password", "error")
            return redirect("/login")

        # Remember which user has logged in
        session["user_id"] = user.id

        return redirect("/")

    else:
        session["animationLoaded"] = True
        return render_template("login.html", animationLoaded=animationLoaded)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        allUsernames = db.session.execute(db.select(User.username)).scalars().all()

        # Ensure user doesn't exist
        if username in allUsernames:
            flash("User already exists", "error")
            return redirect("/register")
        
        # Ensure inputs are submitted
        elif isBlank(username):
            flash("Must provide username", "error")
            return redirect("/register")
        elif isBlank(password):
            flash("Must provide password", "error")
            return redirect("/register")
        elif isBlank(confirmation):
            flash("Must provide a confirmation password", "error")
            return redirect("/register")
        
        # Ensure password equals confirmation
        elif password != confirmation:
            flash("Password does not equal confirmation", "error")
            return redirect("/register")
        else:
            hashedPassword = generate_password_hash(password)
            user = User(username=username, hash=hashedPassword)
            db.session.add(user)
            db.session.commit()
            flash("Your account has been created", "success")
            return redirect("/login")
    else:
        return render_template("register.html")


@app.route("/accounts")
@loginRequired
def accounts():
    userID = session["user_id"]
    accounts = getUserAccounts(userID)
    checkingTotal = getTypeTotals(accounts, "Checking")
    savingsTotal = getTypeTotals(accounts, "Savings")

    return render_template(
        "accounts.html",
        accounts=accounts,
        checkingTotal=checkingTotal,
        savingsTotal=savingsTotal,
    )


@app.route("/transactions")
@loginRequired
def transactions():
    userID = session["user_id"]
    userAccountsID = getUserAccountsID(userID)
    transactions = getAccountsTransactions(userAccountsID)
    return render_template("transactions.html", transactions=transactions)


@app.route("/transfer", methods=["GET", "POST"])
@loginRequired
def transfer():
    userID = session["user_id"]
    if request.method == "POST":

        # Ensure user isn't a guest
        if checkGuest(userID):
            flash("Guests can't input transfers", "error")
            return redirect("/transfer")
        date = request.form.get("date")
        fromID = request.form.get("from")
        toID = request.form.get("to")
        amount = request.form.get("amount")

        # Ensure inputs are submitted
        if isBlank(date):
            flash("Must provide a date", "error")
            return redirect("/transfer")
        if isBlank(amount):
            flash("Must provide an amount", "error")
            return redirect("/transfer")
        if isBlank(fromID):
            flash("Must select an account to transfer from", "error")
            return redirect("/transfer")
        if isBlank(toID):
            flash("Must select an account to transfer to", "error")
            return redirect("/transfer")
        
        # Ensure user isn't transferring to the same account
        if fromID == toID:
            flash("Can't transfer to the same account", "error")
            return redirect("/transfer")
        
        # Ensure amount is a number
        if not isFloat(amount):
            flash("Must input a number for the transfer amount", "error")
            return redirect("/transfer")

        fromID = int(fromID)
        toID = int(toID)
        amount = float(amount)

        fromAccount = getAccount(fromID)
        toAccount = getAccount(toID)

        # Ensure user inputs a positive amount
        if amount <= 0:
            flash("Must input a positive amount", "error")
            return redirect("/transfer")
        
        # Ensure account has enough balance either currently or at the date the transfer is set
        if (fromAccount.balance < amount) or (balanceAtDate(date, fromID) < amount):
            flash("Account does not have enough balance for this transfer", "error")
            return redirect("/transfer")
        
        # Add outgoing transfer transaction
        fromAccount.balance -= amount
        toAccount.balance += amount
        fromTransaction = Transaction(
            account_id=fromID,
            date=date,
            transactionType="Outgoing Transfer",
            name="Transfer to " + toAccount.name,
            category="Outgoing Transfer",
            accountName=fromAccount.name,
            amount=amount,
        )
        db.session.add(fromTransaction)

        # Add incoming transfer transaction
        toTransaction = Transaction(
            account_id=toID,
            date=date,
            transactionType="Incoming Transfer",
            name="Transfer from " + fromAccount.name,
            category="Incoming Transfer",
            accountName=toAccount.name,
            amount=amount,
        )
        db.session.add(toTransaction)
        db.session.commit()
        flash("Transfer successful", "success")
        return redirect("/")
    else:
        accounts = getUserAccounts(userID)
        return render_template("transfer.html", accounts=accounts)


@app.route("/addAccount", methods=["GET", "POST"])
@loginRequired
def addAccount():
    userID = session["user_id"]
    # Add account for user
    if request.method == "POST":

        # Ensure user isn't a guest
        if checkGuest(userID):
            flash("Guests can't add accounts", "error")
            return redirect("/addAccount")

        name = request.form.get("name")
        category = request.form.get("category")

        # Ensure name is submitted
        if isBlank(name):
            flash("Must provide a name", "error")
            return redirect("/addAccount")

        account = Account(user_id=userID, category=category, name=name, balance=0)
        db.session.add(account)
        db.session.commit()
        flash("Account has been added", "success")
        return redirect("/")
    else:
        return render_template("add_accounts.html")


@app.route("/addTransaction", methods=["GET", "POST"])
@loginRequired
def addTransaction():
    # Add transaction to account
    userID = session["user_id"]
    if request.method == "POST":

        # Ensure user isn't a guest
        if checkGuest(userID):
            flash("Guests can't add transactions", "error")
            return redirect("/addTransaction")
        
        # Get data from form
        date = request.form.get("date")
        transactionType = request.form.get("type")
        name = request.form.get("name")
        category = request.form.get("category")
        accountID = request.form.get("account")
        amount = request.form.get("amount")

        # Ensure inputs are submitted
        if isBlank(date):
            flash("Must provide a date", "error")
            return redirect("/addTransaction")
        if isBlank(name):
            flash("Must provide a name", "error")
            return redirect("/addTransaction")
        if isBlank(category):
            flash("Must provide a category", "error")
            return redirect("/addTransaction")
        if isBlank(accountID):
            flash("Must select an account", "error")
            return redirect("/addTransaction")
        if isBlank(amount):
            flash("Must input an amount", "error")
            return redirect("/addTransaction")
        
        # Ensure amount is a number
        if not isFloat(amount):
            flash("Must input a number for the transaction amount", "error")
            return redirect("/addTransaction")

        accountID = int(accountID)
        amount = float(amount)
        account = getAccount(accountID)

        # Ensure user inputs a positive amoount
        if amount <= 0:
            flash("Must input a positive amount", "error")
            return redirect("/addTransaction")

        balance = account.balance
        if transactionType == "Expense":

            # Ensure account has enough balance either currently or at the date the transaction is set
            if (balance < amount) or (balanceAtDate(date, accountID) < amount):
                print(balanceAtDate(date, accountID))
                flash(
                    "Account does not have enough balance for this transaction", "error"
                )
                return redirect("/addTransaction")
            balance -= amount
            account.balance = balance
        else:
            balance += amount
            account.balance = balance

        transaction = Transaction(
            account_id=accountID,
            date=date,
            transactionType=transactionType,
            name=name,
            category=category,
            accountName=account.name,
            amount=amount,
        )
        db.session.add(transaction)
        db.session.commit()
        flash("Transaction has been added", "success")
        return redirect("/")
    else:
        accounts = getUserAccounts(userID)
        return render_template("add_transaction.html", accounts=accounts)


@app.route("/editAccount", methods=["GET", "POST"])
@loginRequired
def editAccount():
    userID = session["user_id"]
    if request.method == "POST":
        accountID = request.form.get("accountID")
        account = getAccount(accountID)

        # Ensure user isn't a guest
        if checkGuest(userID):
            flash("Guests can't modify accounts", "error")
            return render_template(
                "edit_account.html", accountID=accountID, account=account
            )
        name = request.form.get("name")
        category = request.form.get("category")
        
        # Ensure name is submitted
        if isBlank(name):
            flash("Must input a name", "error")
            return render_template(
                "edit_account.html", accountID=accountID, account=account
            )
        account.name = name
        account.category = category
        db.session.commit()
        flash("Account has been modified", "success")
        return redirect("/")
    else:
        accountID = request.args.get("accountID")
        account = getAccount(accountID)
        return render_template(
            "edit_account.html", accountID=accountID, account=account
        )


@app.route("/editTransaction", methods=["GET", "POST"])
@loginRequired
def editTransaction():
    userID = session["user_id"]
    if request.method == "POST":
        transactionID = request.form.get("transactionID")
        transaction = getTransaction(transactionID)

        # Ensure user isn't a guest
        if checkGuest(userID):
            flash("Guests can't modify transactions", "error")
            return render_template(
                "edit_transaction.html",
                transactionID=transactionID,
                transaction=transaction,
            )
        name = request.form.get("name")
        category = request.form.get("category")

        # Ensure inputs are submitted
        if isBlank(name):
            flash("Must input a name", "error")
            return render_template(
                "edit_transaction.html",
                transactionID=transactionID,
                transaction=transaction,
            )
        if isBlank(category):
            flash("Must input a category", "error")
            return render_template(
                "edit_transaction.html",
                transactionID=transactionID,
                transaction=transaction,
            )
        transaction.name = name
        transaction.category = category
        db.session.commit()
        flash("Transaction has been modified", "success")
        return redirect("/")
    else:
        transactionID = request.args.get("transactionID")
        transaction = getTransaction(transactionID)
        return render_template(
            "edit_transaction.html",
            transactionID=transactionID,
            transaction=transaction,
        )


@app.route("/deleteAccount", methods=["POST"])
@loginRequired
def deleteAccount():
    userID = session["user_id"]
    if request.method == "POST":
        accountID = request.form.get("accountID")
        account = getAccount(accountID)

        # Ensure user isn't a guest
        if checkGuest(userID):
            flash("Guests can't delete accounts", "error")
            return render_template(
                "edit_account.html", accountID=accountID, account=account
            )
        # Delete transactions for account
        transactions = getAccountTransactions(accountID)
        for transaction in transactions:
            db.session.delete(transaction)
        db.session.delete(account)
        db.session.commit()
        flash("Account has been deleted", "success")
        return redirect("/")


@app.route("/deleteTransaction", methods=["POST"])
@loginRequired
def deleteTransaction():
    userID = session["user_id"]
    if request.method == "POST":
        transactionID = request.form.get("transactionID")
        transaction = getTransaction(transactionID)

        # Ensure user isn't a guest
        if checkGuest(userID):
            flash("Guests can't delete transactions", "error")
            return render_template(
                "edit_transaction.html",
                transactionID=transactionID,
                transaction=transaction,
            )
        # Find account
        account = getAccount(transaction.account_id)
        if transaction.transactionType == "Expense":
            account.balance += transaction.amount
        else:
            if account.balance < transaction.amount:
                flash(
                    "Deleting this transaction will make the account balance negative",
                    "error",
                )
                return render_template(
                    "edit_transaction.html",
                    transactionID=transactionID,
                    transaction=transaction,
                )
            account.balance -= transaction.amount
        db.session.delete(transaction)
        db.session.commit()
        flash("Transaction has been deleted", "success")
        return redirect("/")
