from flask import render_template, flash, redirect, g, request, url_for, jsonify
from app import app, db
from models import Ticket, Invoice
from forms import TicketForm 
from flask.ext.security import login_required, current_user
from config import BLOCKCHAIN_URL, SECRET_KEY, STASH_WALLET, PRICE_OF_SERVICE, CONFIRMATION_CAP
import simplejson as json
import urllib2

# Page routes
@app.route('/')
@app.route('/index')
def index():
    user = g.user
    return render_template("index.html", user=user)

@app.route('/blog')
def blog():
    return "Da Blog!"

@app.route('/dashboard')
@login_required
def dashboard():
    user = g.user
    latest_invoice = user.invoices.order_by(Invoice.datepaid.desc()).first()
    lastpaid = latest_invoice.datepaid if latest_invoice else "Unpurchased"
    expires = latest_invoice.dateends if latest_invoice else "No service enabled"
    return render_template("dashboard.html", user=user, latest=latest_invoice, lastpaid=lastpaid, expires=expires)

@app.route('/newticket', methods=['GET', 'POST'])
@login_required
def newticket():
    user = g.user
    form = TicketForm()
    if form.validate_on_submit():
        import datetime
        t = Ticket()
        form.populate_obj(t)
        t.timestamp = datetime.datetime.utcnow()
        t.created = datetime.datetime.utcnow()
        t.user_id = user.id
        db.session.add(t);
        db.session.commit()

        flash('New ticket submitted: ' + form.subject.data)
        return redirect('/dashboard')
    return render_template('newticket.html', form=form, user=user)

@app.route('/viewticket/<int:tid>', methods=['GET', 'POST'])
@login_required
def viewticket(tid):
    user = g.user
    t = Ticket.query.get(tid)
    return render_template('viewticket.html', user=user, ticket=t)

@app.route('/editticket/<int:tid>', methods=['GET', 'POST'])
@login_required
def editticket(tid):
    user = g.user
    t = Ticket.query.get(tid)
    form = TicketForm(subject=t.subject, body=t.body)
    if form.validate_on_submit():
        import datetime
        form.populate_obj(t)
        t.timestamp = datetime.datetime.utcnow()
        flash("Updated ticket: " + t.subject)
        db.session.commit()
        return redirect('/dashboard')
    return render_template('editticket.html', user=user, ticket=t, form=form)

@app.route('/deleteticket/<int:tid>', methods=['GET', 'POST'])
@login_required
def deleteticket(tid):
    user = g.user
    t = Ticket.query.get(tid)
    return render_template('viewticket.html', user=user, ticket=t)

# Start Bitcoin stuff -- blockchain.info api
@app.route('/purchase')
def purchase():
    user = g.user
    try:
        exchange_data = json.load(urllib2.build_opener().open(urllib2.Request("http://blockchain.info/tobtc?currency=USD&value=30")))
    except urllib2.URLError as e:
        flash('Unable to fetch current BTC exchange rate.')
        return render_template('purchase.html', user=user, price=0, service_price=PRICE_OF_SERVICE)
    return render_template('purchase.html', user=user, price=str(exchange_data), service_price=PRICE_OF_SERVICE)

@app.route('/confirm_purchase/', defaults={'invoice_id': None})
@app.route('/confirm_purchase/<int:invoice_id>', methods=['GET', 'POST'])
@login_required
def confirm_purchase(invoice_id):
    import datetime
    user = g.user
    if invoice_id is None:
        i = Invoice()
        i.paid = False
        i.datecreated = datetime.datetime.utcnow()
        i.user_id = user.id
        db.session.add(i)
        db.session.commit()
        try:
            callback_url = url_for('pay_invoice', _external=True)+'?secret='+SECRET_KEY+'%26invoice_id='+str(i.id)
            url = BLOCKCHAIN_URL+'?method=create&address='+STASH_WALLET+'&callback='+callback_url
            xhr = urllib2.Request(url)
            data = json.load(urllib2.build_opener().open(xhr))
            price_data = json.load(urllib2.build_opener().open(urllib2.Request("http://blockchain.info/tobtc?currency=USD&value="+str(PRICE_OF_SERVICE))))
            exchange_data = json.load(urllib2.build_opener().open(urllib2.Request("http://blockchain.info/ticker")))
            app.logger.info("Sent to blockchain api: " + url)
        except urllib2.URLError as e:
            app.logger.error('Unable to access the blockchain.info api: ' + url)
            flash('There was an error creating a new invoice. Please try again later.')
            return redirect('/dashboard')
        i.address = data['input_address']
        i.total_btc = price_data
        i.exchange_rate_when_paid = exchange_data['USD']['last']
        db.session.commit()
        # TODO: Generate a QR code and/or other e-z payment options for BTC services
        return redirect(url_for('confirm_purchase', invoice_id=i.id))
    else:
        i = Invoice.query.get(invoice_id)
        if request.method == 'POST':
            flash('Invoice ('+i.address+') was deleted succesfully.')
            db.session.delete(i)
            db.session.commit()
            return redirect(url_for('dashboard'))
        return render_template('confirm_purchase.html', user=user, invoice=i, min_confirm=CONFIRMATION_CAP)


# AJAX Callbacks
@app.route('/invoice_status', methods=['POST'])
def invoice_status():
    data = request.form
    i = Invoice.query.get(data['invoice_id'])
    if i is None:
        return 0
    return jsonify({
        'confirmations': i.confirmations,
        'value_paid': i.value_paid,
        'total_btc': i.total_btc,
        'input_transaction_hash': i.input_transaction_hash
        })

@app.route('/pay_invoice', methods=['GET'])
def pay_invoice():
    data = request.args
    if 'test' in data:
        app.logger.info('Test response recieved from Blockchain.info. return: *test*')
        return "*test*"
    if 'secret' in data and data['secret'] == SECRET_KEY:
        import datetime
        i = Invoice.query.get(data['invoice_id'])
        if i is None: 
            # could not find invoice - do we ignore or create?
            app.logger.info("Callback received for non-existant invoice. return: *error*")
            return "*error*"
        if not i.paid:
            i.value_paid = float(data['value']) / 100000000
        else:
            i.value_paid += float(data['value']) / 100000000
        i.datepaid = datetime.datetime.utcnow()
        i.confirmations = data['confirmations']
        i.transaction_hash = data['transaction_hash']
        i.input_transaction_hash = data['input_transaction_hash']
        if i.value_paid == i.total_btc:
            app.logger.info("Invoice {} paid on {} for {} BTC.".format(i.id, i.datepaid, i.value_paid))
            i.paid = True
        db.session.commit()
        if i.paid and i.confirmations > CONFIRMATION_CAP:
            app.logger.info("Invoice {} was confirmed at {}. return: *ok*".format(i.id, i.datepaid))
            i.is_confirmed = True
            i.dateends = i.datepaid + datetime.timedelta(weeks=4)
            return "*ok*"
        app.logger.info("Callback received for invoice {}: awaiting confirmation (current: {}). return: *unconfirmed*".format(i.id, i.confirmations))
        return "*unconfirmed*"
    else:
        app.logger.info('Payment callback with invalid secret key recieved. return: *error*')
        return "*error*"

# Not routes
@app.errorhandler(404)
def internal_error(error):
    return render_template('error.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('error.html'), 500

@app.before_request
def before_request():
    g.user = current_user

@app.template_filter('date')
def _jinja2_filter_datetime(date, fmt=None):
    if not date:
        return None
    if fmt:
        return date.strftime(fmt)
    else:
        return date.strftime("%m/%d/%y (%I:%M%p)")
