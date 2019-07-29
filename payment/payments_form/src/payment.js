import React, {Component} from 'react';
import ReactDOM from 'react-dom';
import loader from './loader.svg';
import SVG from 'react-inlinesvg';

const supportedInstruments = [{
    supportedMethods: ['basic-card'],
    data: {
        supportedNetworks: [
            'visa', 'mastercard', 'amex', 'diners', 'jcb', 'cartebancaire'
        ]
    }
}];

const worldPayTestKey = "T_C_52bc5b16-562d-4198-95d4-00b91f30fe2c";


class PaymentForm extends Component {
    constructor(props) {
        super(props);

        this.state = {
            payment: null,
            err: null,
            selectedMethod: null,
        };

        this.handleError = this.handleError.bind(this);
        this.updatePayment = this.updatePayment.bind(this);
        this.paymentDetails = this.paymentDetails.bind(this);
        this.paymentOptions = this.paymentOptions.bind(this);
        this.canUsePaymentRequests = this.canUsePaymentRequests.bind(this);
        this.makePaymentRequest = this.makePaymentRequest.bind(this);
        this.takePayment = this.takePayment.bind(this);
        this.basicCardToWorldPayToken = this.basicCardToWorldPayToken.bind(this);
    }

    updatePayment() {
        fetch(`/payment/${this.props.paymentId}/`)
            .then(resp => {
                if (resp.ok) {
                    return resp.json();
                } else {
                    throw new Error('Something went wrong');
                }
            })
            .then(resp => {
                this.setState({
                    payment: resp
                });
                this.canUsePaymentRequests()
                    .then(value => this.setState({
                        selectedMethod: value ? "payment-requests" : "form"
                    }))
                    .catch(err => this.handleError());
            })
            .catch(err => this.handleError())
    }

    componentDidMount() {
        this.updatePayment();
    }

    handleError(err) {
        let error = (err === undefined) ? "Something went wrong, please try again." : err;
        this.setState({
            err: error
        })
    }

    paymentDetails() {
        const total = this.state.payment.items.reduce((prev, item) => prev + item.price, 0.0);

        return {
            id: this.state.payment.id,
            total: {
                label: 'Total',
                amount: {
                    currency: 'GBP',
                    value: total
                }
            },
            displayItems: this.state.payment.items.map(item => {
                return {
                    label: item.title,
                    amount: {
                        currency: 'GBP',
                        value: item.price,
                    }
                }
            })
        }
    }

    paymentOptions() {
        if (this.state.payment.customer === null) {
            return {
                requestPayerPhone: true,
                requestPayerName: true,
                requestPayerEmail: true,
            }
        } else {
            return {}
        }
    }

    canUsePaymentRequests() {
        return new Promise((resolve, reject) => {
            if (!window.PaymentRequest) {
                resolve(false);
            }
            resolve(true);
        });
    }

    makePaymentRequest() {
        let request = new PaymentRequest(supportedInstruments, this.paymentDetails(), this.paymentOptions());
        request.show()
            .then(res => {
                if (res.methodName === "basic-card") {
                    this.basicCardToWorldPayToken(res.details)
                        .then(token => {
                            this.takePayment(res, token)
                        })
                        .catch(err => {
                            res.complete("fail")
                                .then(() => {
                                    this.handleError(`Payment failed: ${err.message}`)
                                })
                        })
                } else {
                    this.handleError()
                }
            })
            .catch(err => {
                if (err.name === "NotSupportedError") {
                    this.setState({
                        selectedMethod: 'form'
                    });
                }
            })
    }

    takePayment(res, token) {
        res.complete('success').then(() => {
            this.props.onComplete();
        }).catch(() => {
            this.handleError()
        });
    }

    basicCardToWorldPayToken(res) {
        return new Promise((resolve, reject) => {
            const token = (this.state.payment.environment === "T") ? worldPayTestKey : null;

            if (token === null) {
                reject(new Error("No token available"));
            }

            fetch("https://api.worldpay.com/v1/tokens", {
                method: "POST",
                body: JSON.stringify({
                    reusable: false,
                    paymentMethod: {
                        name: res.cardholderName,
                        expiryMonth: res.expiryMonth,
                        expiryYear: res.expiryYear,
                        cardNumber: res.cardNumber,
                        type: "Card",
                        cvc: res.cardSecurityCode,
                    },
                    clientKey: token
                })
            })
                .then(resp => {
                    if (resp.ok) {
                        return resp.json();
                    } else {
                        resp.json()
                            .then(resp => {
                                throw new Error(resp.message);
                            })
                            .catch(err => reject(err));
                    }
                })
                .then(resp => {
                    resolve(resp.token);
                })
                .catch(err => {
                    reject(err);
                })
        });
    }

    render() {
        if (this.state.err != null) {
            return <h3>{this.state.err}</h3>
        } else if (this.state.payment === null || this.state.selectedMethod === null) {
            return <SVG src={loader} className="loader"/>
        } else {
            if (this.state.selectedMethod === "payment-requests") {
                return <React.Fragment>
                    <button onClick={this.makePaymentRequest}>
                        Pay
                    </button>
                    <a href="#" onClick={() => {
                        this.setState({selectedMethod: "form"})
                    }}>
                        Enter card details manually
                    </a>
                </React.Fragment>;
            } else if (this.state.selectedMethod === "form") {
                return "Form";
            }
        }
    }
}

window.makePaymentForm = (container, payment_id, on_complete) => {
    ReactDOM.render(<PaymentForm paymentId={payment_id} onComplete={on_complete}/>, container);
};