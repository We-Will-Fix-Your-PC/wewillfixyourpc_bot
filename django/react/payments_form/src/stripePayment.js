import React, {Component} from 'react';
import 'whatwg-fetch';
import {CardElement, Elements, injectStripe, StripeProvider, PaymentRequestButtonElement} from 'react-stripe-elements';
import {API_ROOT} from "./payment";
import * as Sentry from "@sentry/browser";

const STRIPE_TEST_KEY = "pk_test_HiLhXV0p2Gk4HzYr5S5vpmbi00pSy0cAV";
const STRIPE_LIVE_KEY = "pk_live_VLsjEC8QBoN5rQWW0rfVccqW00VzaknDP";

class StripePayment extends Component {
    render() {
        return <React.Fragment>
            {this.props.paymentRequest ?
                <PaymentRequestButtonElement paymentRequest={this.props.paymentRequest}/> : null}
            <CardElement/>
            <button type="submit">Submit</button>
        </React.Fragment>
    }
}

const StripePaymentInjected = injectStripe(StripePayment);

export default class StripeWrapper extends Component {
    constructor(props) {
        super(props);

        this.state = {
            payment: null,
            err: null,
            stripe: null,
            paymentRequest: null
        };
    }

    updatePayment() {
        this.setState({
            payment: null,
            err: null,
            stripe: null,
            paymentRequest: null
        });

        if (this.props.paymentId) {
            fetch(`${API_ROOT}payment/${this.props.paymentId}/`)
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

                    let stripe = null;
                    if (resp.enviroment !== "T") {
                        stripe = window.Stripe(STRIPE_LIVE_KEY);
                    } else {
                        stripe = window.Stripe(STRIPE_TEST_KEY);
                    }

                    const paymentRequest = stripe.paymentRequest({
                        country: 'GB',
                        currency: 'gbp',
                        total: {
                            label: 'Total',
                            amount: (resp.items.reduce((prev, item) => prev + item.price, 0.0) * 100),
                        },
                        displayItems: resp.items.map(item => {
                            return {
                                label: item.title,
                                amount: item.price*100,
                            }
                        }),
                        requestPayerName: resp.customer === null,
                        requestPayerEmail: resp.customer === null,
                        requestPayerPhone: resp.customer === null,
                    });
                    paymentRequest.canMakePayment().then(res => {
                        if (res) {
                            this.setState({
                                paymentRequest: paymentRequest
                            })
                        }
                    });

                    this.setState({
                        payment: resp,
                        stripe: stripe,
                    });
                })
                .catch(err => this.handleError(err))
        }
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

    componentDidMount() {
        this.updatePayment();
    }

    render() {
        return <StripeProvider stripe={this.state.stripe}>
            <Elements>
                <StripePaymentInjected paymentRequest={this.state.paymentRequest}/>
            </Elements>
        </StripeProvider>
    }
}