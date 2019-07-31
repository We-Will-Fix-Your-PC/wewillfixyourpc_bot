import React, {Component} from 'react';
import * as Sentry from '@sentry/browser';
import ReactDOM from 'react-dom';
import uuid from 'uuid';
import loader from './loader.svg';
import SVG from 'react-inlinesvg';
import CardForm from './cardForm';
import GPayButton from './gpayButton';

const ROOT_URL = 'https://3f092962.eu.ngrok.io/';

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

const allowedCardNetworks = ["AMEX", "DISCOVER", "INTERAC", "JCB", "MASTERCARD", "VISA"];
const allowedCardAuthMethods = ["PAN_ONLY"];
const testTokenizationSpecification = {
    type: 'DIRECT',
    parameters: {
        protocolVersion: "ECv2",
        publicKey: "BMfHP71Jz1LtG0G0rUENWmInA1+gHndceODwxKOvJvKHPOaqKWZfkJIB2Ga8fWFg4HbQC7fKju8J7x23hOEqJ74="
    }
};

const googlePaymentTestBaseRequest = {
    apiVersion: 2,
    apiVersionMinor: 0,
    merchantInfo: {
        merchantName: 'We Will Fix Your PC'
    },
};

const googlePayBaseCardPaymentMethod = {
    type: 'CARD',
    parameters: {
        allowedAuthMethods: allowedCardAuthMethods,
        allowedCardNetworks: allowedCardNetworks,
        billingAddressRequired: true,
        billingAddressParameters: {
            format: "FULL",
        },
    }
};

const googlePaymentTestDataRequest = {
    supportedMethods: 'https://google.com/pay',
    data: Object.assign({
        environment: 'TEST',
        allowedPaymentMethods: [
            Object.assign({tokenizationSpecification: testTokenizationSpecification},
                googlePayBaseCardPaymentMethod)
        ]
    }, googlePaymentTestBaseRequest)
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
            canUsePaymentRequests: null,
            googlePaymentsClient: null,
            isGooglePayReady: null
        };

        this.handleError = this.handleError.bind(this);
        this.onComplete = this.onComplete.bind(this);
        this.updatePayment = this.updatePayment.bind(this);
        this.paymentTotal = this.paymentTotal.bind(this);
        this.paymentDetails = this.paymentDetails.bind(this);
        this.paymentOptions = this.paymentOptions.bind(this);
        this.googlePaymentRequest = this.googlePaymentRequest.bind(this);
        this.canUsePaymentRequests = this.canUsePaymentRequests.bind(this);
        this.makePaymentRequest = this.makePaymentRequest.bind(this);
        this.makeGooglePayment = this.makeGooglePayment.bind(this);
        this.onFormSubmit = this.onFormSubmit.bind(this);
        this.takeBasicPayment = this.takeBasicPayment.bind(this);
        this.takeGooglePayment = this.takeGooglePayment.bind(this);
        this.takePayment = this.takePayment.bind(this);
        this.basicCardToWorldPayToken = this.basicCardToWorldPayToken.bind(this);
        this.handlePaymentRequest = this.handlePaymentRequest.bind(this);
        this.handleMessage = this.handleMessage.bind(this);
        this.handleTryAgain = this.handleTryAgain.bind(this);
    }

    updatePayment() {
        this.setState({
            payment: null,
            err: null,
            selectedMethod: null,
            threedsData: null,
            complete: false,
            loading: false,
            canUsePaymentRequests: null,
            googlePaymentsClient: null,
            isGooglePayReady: null
        });

        const checkMethods = (resp) => {
            this.canUsePaymentRequests()
                .then(value => this.setState({
                    canUsePaymentRequest: value
                }))
                .catch(err => this.handleError(err));
            if (resp.environment === "T") {
                const paymentsClient = new window.google.payments.api.PaymentsClient({environment: 'TEST'});
                this.setState({
                    googlePaymentsClient: paymentsClient
                });
                const isReadyToPayRequest = Object.assign({}, googlePaymentTestBaseRequest);
                isReadyToPayRequest.allowedPaymentMethods = [googlePayBaseCardPaymentMethod];
                paymentsClient.isReadyToPay(isReadyToPayRequest)
                    .then(resp => {
                        if (resp.result) {
                            this.setState({
                                isGooglePayReady: true
                            });
                            paymentsClient.prefetchPaymentData(this.googlePaymentRequest());
                        } else {
                            this.setState({
                                isGooglePayReady: false
                            });
                        }
                    })
                    .catch(err => this.handleError(err));
            } else {
                this.setState({
                    isGooglePayReady: false,
                });
            }
        };

        if (this.props.paymentId) {
            fetch(`/payment/${this.props.paymentId}/`)
                .then(resp => {
                    if (resp.ok) {
                        return resp.json();
                    } else {
                        throw new Error('Something went wrong');
                    }
                })
                .then(resp => {
                    if (resp.state !== "O") {
                        this.handleError();
                        return;
                    }
                    this.setState({
                        payment: resp
                    });
                    checkMethods(resp);
                })
                .catch(err => this.handleError(err))
        } else {
            const payment = this.props.payment;
            payment.id = uuid.v4();
            payment.new = true;

            if (!payment.environment) {
                payment.environment = "T";
            }

            this.setState({
                payment: payment
            });

            checkMethods(payment);
        }
    }

    componentDidMount() {
        this.updatePayment();
        window.addEventListener("message", this.handleMessage, false);
    }

    handleError(err, message) {
        if (err) {
            console.error(err);
             const eventId = Sentry.captureException(err);
             this.setState({
                 errId: eventId
             })
        }
        let error_msg = (message === undefined) ? "Something went wrong" : message;
        this.setState({
            err: error_msg,
            loading: false,
        })
    }

    paymentTotal() {
        return this.state.payment.items.reduce((prev, item) => prev + item.price, 0.0);
    }

    paymentDetails() {
        const total = this.paymentTotal();

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
                        .then(() => {
                            this.handleError(err, "Payment failed")
                        })
                        .catch(err => {
                            this.handleError(err);
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

    googlePaymentRequest() {
        if (this.state.payment.environment === "T") {
            const paymentDataRequest = Object.assign({}, googlePaymentTestBaseRequest);
            paymentDataRequest.allowedPaymentMethods = [
                Object.assign({tokenizationSpecification: testTokenizationSpecification},
                    googlePayBaseCardPaymentMethod)
            ];
            paymentDataRequest.transactionInfo = {
                totalPriceStatus: 'FINAL',
                totalPrice: this.paymentTotal().toString(),
                currencyCode: 'GBP'
            };
            if (this.state.payment.customer === null) {
                paymentDataRequest.emailRequired = true;
            }
            return paymentDataRequest;
        }
    }

    makeGooglePayment() {
        const paymentDataRequest = this.googlePaymentRequest();
        this.state.googlePaymentsClient.loadPaymentData(paymentDataRequest).then((paymentData) => {
            console.log(paymentData);
            this.takeGooglePayment({
                details: paymentData,
                payerEmail: paymentData.email,
                payerName: paymentData.paymentMethodData.info.billingAddress.name,
                complete: () => Promise.resolve(true)
            });
        }).catch((err) => {
            if (err.statusCode !== "CANCELED") {
                this.handleError(err);
            }
        });
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
            accepts: this.props.acceptsHeader
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

        if (this.state.payment.new) {
            data.payment = this.state.payment;
        }

        fetch(`${ROOT_URL}payment/worldpay/${this.state.payment.id}/`, {
            method: "POST",
            credentials: 'include',
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
                            this.onComplete();
                        })
                        .catch(err => this.handleError(err))
                } else if (resp.state === "3DS") {
                    res.complete('success')
                        .then(() => {
                            this.setState({
                                threedsData: resp
                            });
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
            .catch(err => {
                res.complete('fail')
                    .then(() => {
                        this.handleError(null, "Payment failed")
                    })
                    .catch(err => this.handleError(err))
            })
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

    onComplete() {
        this.setState({
            complete: true,
            loading: false,
        });
        this.props.onComplete(this.state.payment.id)
    }

    handleMessage(event) {
        if (this.state.threedsData !== null) {
            if (event.data.type !== "3DS") {
                return;
            }
            if (event.data.payment_id !== this.state.payment.id) {
                this.handleError();
            }
            if (event.data.threeds_approved) {
                this.onComplete();
            } else {
                this.handleError(null, "Payment failed");
            }
        }
    }

    handleTryAgain(e) {
        e.preventDefault();
        this.updatePayment();
    }

    render() {
        if (this.state.err != null) {
            return <React.Fragment>
                <h3>{this.state.err}</h3>
                <div className="buttons">
                    <button onClick={this.handleTryAgain}>Try again</button>
                    {this.state.errId ? <button onClick={() => {
                        Sentry.showReportDialog({ eventId: this.state.errId })
                    }}>Report feedback</button> : null}
                </div>
            </React.Fragment>;
        } else if (this.state.complete) {
            return <h3>Payment successful</h3>;
        } else if (this.state.payment === null || this.state.canUsePaymentRequest === null ||
            this.state.isGooglePayReady === null) {
            return <SVG src={loader} className="loader"/>
        } else if (this.state.threedsData !== null) {
            return <iframe src={this.state.threedsData.frame} width={390} height={400}/>
        } else {
            if ((this.state.canUsePaymentRequest || this.state.isGooglePayReady)
                && this.state.selectedMethod !== "form") {
                return <div className="buttons">
                    {this.state.isGooglePayReady ?
                        <GPayButton paymentsClient={this.state.googlePaymentsClient}
                                    onClick={this.makeGooglePayment}/> : null}
                    {this.state.canUsePaymentRequest ? <button onClick={this.makePaymentRequest}>
                        Autofill from browser
                    </button> : null}
                    <a href="" onClick={(e) => {
                        e.preventDefault();
                        this.setState({selectedMethod: "form"})
                    }}>
                        Enter card details manually
                    </a>
                </div>;
            } else {
                if (!this.state.loading) {
                    const paymentOptions = this.paymentOptions();

                    return <CardForm paymentOptions={paymentOptions} payment={this.state.payment}
                                     onSubmit={this.onFormSubmit}/>;
                } else {
                    return <SVG src={loader} className="loader"/>
                }
            }
        }
    }
}

window.addEventListener("onload", () => {
    Sentry.init({dsn: "https://3407347031614995bc8207f089a10f92@sentry.io/1518060"});
});

window.makePaymentForm = (container, payment_id, on_complete, accepts_header) => {
    ReactDOM.render(<PaymentForm acceptsHeader={accepts_header} paymentId={payment_id}
                                 onComplete={on_complete}/>, container);
};
window.makePaymentFormFromData = (container, payment, on_complete, accepts_header) => {
    ReactDOM.render(<PaymentForm acceptsHeader={accepts_header} payment={payment}
                                 onComplete={on_complete}/>, container);
};