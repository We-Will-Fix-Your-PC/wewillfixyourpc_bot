import React, {Component} from 'react';
import ReactDOM from 'react-dom';
import loader from './loader.svg';
import SVG from 'react-inlinesvg';
import CardForm from './cardForm';

const basicCardInstrument = {
    supportedMethods: 'basic-card',
    data: {
        supportedNetworks: [
            'visa', 'mastercard', 'amex', 'diners', 'jcb', 'cartebancaire'
        ]
    }
};

const worldPayTestKey = "T_C_52bc5b16-562d-4198-95d4-00b91f30fe2c";
const worldPayLiveKey = "L_C_4a900284-cafb-41fd-a544-8478429f539b";

const googlePaymentTestDataRequest = {
    supportedMethods: 'https://google.com/pay',
    data: {
        environment: 'TEST',
        apiVersion: 2,
        apiVersionMinor: 0,
        merchantInfo: {
            merchantName: 'We Will Fix Your PC'
        },
        allowedPaymentMethods: [{
            type: 'CARD',
            parameters: {
                allowedAuthMethods: ["PAN_ONLY"],
                allowedCardNetworks: ["AMEX", "DISCOVER", "JCB", "MASTERCARD", "VISA"],
                billingAddressRequired: true,
                billingAddressParameters: {
                    format: "FULL",
                },
            },
            tokenizationSpecification: {
                type: 'DIRECT',
                parameters: {
                    protocolVersion: "ECv2",
                    publicKey: "BMfHP71Jz1LtG0G0rUENWmInA1+gHndceODwxKOvJvKHPOaqKWZfkJIB2Ga8fWFg4HbQC7fKju8J7x23hOEqJ74="
                }
            }
        }]
    }
};

class PaymentForm extends Component {
    constructor(props) {
        super(props);

        this.state = {
            payment: null,
            err: null,
            selectedMethod: null,
            threedsData: null,
            loading: false,
            complete: false,
        };

        this.form = React.createRef();

        this.handleError = this.handleError.bind(this);
        this.updatePayment = this.updatePayment.bind(this);
        this.paymentDetails = this.paymentDetails.bind(this);
        this.paymentOptions = this.paymentOptions.bind(this);
        this.canUsePaymentRequests = this.canUsePaymentRequests.bind(this);
        this.makePaymentRequest = this.makePaymentRequest.bind(this);
        this.onFormSubmit = this.onFormSubmit.bind(this);
        this.takeBasicPayment = this.takeBasicPayment.bind(this);
        this.takeGooglePayment = this.takeGooglePayment.bind(this);
        this.takePayment = this.takePayment.bind(this);
        this.basicCardToWorldPayToken = this.basicCardToWorldPayToken.bind(this);
        this.handlePaymentRequest = this.handlePaymentRequest.bind(this);
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
                    .catch(err => this.handleError(err));
            })
            .catch(err => this.handleError(err))
    }

    componentDidMount() {
        this.updatePayment();
    }

    handleError(err, message) {
        console.log(err ? err.message : null);
        let error_msg = (message === undefined) ? "Something went wrong" : message;
        this.setState({
            err: error_msg,
            loading: false,
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
        let methods = [];
        if (this.state.payment.environment === "T") {
            methods = [googlePaymentTestDataRequest];
        }
        methods.push(basicCardInstrument);
        let request = new PaymentRequest(methods, this.paymentDetails(), this.paymentOptions());
        request.show()
            .then(res => {
                this.handlePaymentRequest(res)
            })
            .catch(err => {
                if (err.name === "NotSupportedError") {
                    this.setState({
                        selectedMethod: 'form'
                    });
                }
            })
    }

    handlePaymentRequest(res) {
        if (res.methodName === "basic-card") {
            this.basicCardToWorldPayToken(res.details)
                .then(token => {
                    this.takeBasicPayment(res, token)
                })
                .catch(err => {
                    res.complete("fail")
                        .then(err => {
                            this.handleError(err, `Payment failed: ${err.message}`)
                        })
                })
        } else if (res.methodName === "https://google.com/pay") {
            this.takeGooglePayment(res);
        } else {
            res.complete('fail')
                .then(() => this.handleError(null))
                .catch(err => this.handleError(err));
        }
    }

    onFormSubmit(res) {
        this.setState({
            loading: true,
        });
        this.handlePaymentRequest(res);
    }

    takeBasicPayment(res, token) {
        let data = {
            token: token,
            billingAddress: res.details.billingAddress,
            name: res.details.cardholderName,
            accepts: this.props.acceptsHeader,
        };
        this.takePayment(res, data);
    }

    takeGooglePayment(res) {
        let billingAddress = res.details.paymentMethodData.info.billingAddress;
        let data = {
            billingAddress: {
                    addressLine: [billingAddress.address1, billingAddress.address2, billingAddress.address3],
                    country: billingAddress.countryCode,
                    city: billingAddress.locality,
                    dependentLocality: billingAddress.administrativeArea,
                    organization: "",
                    phone: "",
                    postalCode: billingAddress.postalCode,
                    recipient: billingAddress.name,
                    region: "",
                    regionCode: "",
                    sortingCode: billingAddress.sortingCode
                },
            name: billingAddress.name,
            accepts: this.props.acceptsHeader,
            googleData: res.details.paymentMethodData.tokenizationData.token
        };
        this.takePayment(res, data);
    }

    takePayment(res, data) {
        if (res.payerPhone) {
            data.phone = res.payerPhone
        }
        if (res.payerEmail) {
            data.email = res.payerEmail
        }
        if (res.payerName) {
            data.payerName = res.payerName
        }

        fetch(`/payment/worldpay/${this.props.paymentId}/`, {
            method: "POST",
            headers: {
                "X-CSRFToken": document.getElementsByName('csrfmiddlewaretoken')[0].value
            },
            body: JSON.stringify(data)
        })
            .then(resp => {
                if (resp.ok) {
                    return resp.json();
                } else {
                    throw new Error('Something went wrong');
                }
            })
            .then(resp => {
                if (resp.state === "SUCCESS") {
                    res.complete('success')
                        .then(() => {
                            this.setState({
                                complete: true,
                                loading: false,
                            });
                            this.props.onComplete()
                        })
                        .catch(err => this.handleError(err))
                } else if (resp.state === "3DS") {
                    res.complete('success')
                        .then(() => {
                            this.setState({
                                threedsData: resp
                            });
                            while (this.form.current === null) {
                            }
                            this.form.current.submit();
                        })
                        .catch(err => this.handleError(err))
                } else if (resp.state === "FAILED") {
                    res.complete('fail')
                        .then(() => {
                            this.handleError(null, "Payment failed")
                        })
                        .catch(err => this.handleError(err))
                } else {
                    this.handleError(null)
                }
            })
            .catch(err => this.handleError(err))
    }

    basicCardToWorldPayToken(res) {
        return new Promise((resolve, reject) => {
            const token = (this.state.payment.environment === "L") ? worldPayLiveKey : worldPayTestKey;

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
            return <React.Fragment>
                <h3>{this.state.err}</h3>
                <a href="#" onClick={() => window.location.reload()}>Try again</a>
            </React.Fragment>;
        } else if (this.state.complete) {
            return <h3>Payment successful</h3>;
        } else if (this.state.payment === null || this.state.selectedMethod === null) {
            return <SVG src={loader} className="loader"/>
        } else if (this.state.threedsData !== null) {
            return <form ref={this.form} action={this.state.threedsData.redirectURL} method="POST">
                <input type="hidden" name="PaReq" value={this.state.threedsData.oneTime3DsToken}/>
                <input type="hidden" name="TermUrl"
                       value={window.location.origin + window.location.pathname + "3ds?sess_id="
                       + this.state.threedsData.sessionID}/>
                <input type="hidden" name="MD" value={this.state.threedsData.orderCode}/>
            </form>
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
                if (!this.state.loading) {
                    const paymentOptions = this.paymentOptions();

                    return <CardForm paymentOptions={paymentOptions} onSubmit={this.onFormSubmit}/>;
                } else {
                    return <SVG src={loader} className="loader"/>
                }
            }
        }
    }
}

window.makePaymentForm = (container, payment_id, on_complete, accepts_header) => {
    ReactDOM.render(<PaymentForm acceptsHeader={accepts_header} paymentId={payment_id}
                                 onComplete={on_complete}/>, container);
};