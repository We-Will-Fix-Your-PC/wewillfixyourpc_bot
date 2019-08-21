'use strict';

import React from 'react';
import * as Sentry from '@sentry/browser';
import ReactDOM from 'react-dom';
import WorldpayPayment from './worldpayPayment';
import StripePayment from './stripePayment';

export const API_ROOT = process.env.BASE_URL ? process.env.BASE_URL :
    process.env.NODE_ENV  === 'production' ? 'https://bot.cardifftec.uk/' : 'https://wewillfixyourpc-bot.eu.ngrok.io/';

const payment_provider = process.env.PAYMENT_PROVIDER ? process.env.PAYMENT_PROVIDER : "STRIPE";

window.addEventListener("onload", () => {
    Sentry.init({dsn: "https://3407347031614995bc8207f089a10f92@sentry.io/1518060"});
});

window.makePaymentForm = (container, payment_id, on_complete, accepts_header) => {
    if (payment_provider === "WORLDPAY") {
        ReactDOM.render(<WorldpayPayment acceptsHeader={accepts_header} paymentId={payment_id}
                                         onComplete={on_complete}/>, container);
    } else if (payment_provider === "STRIPE") {
        ReactDOM.render(<StripePayment paymentId={payment_id} onComplete={on_complete}/>, container);
    }
};
window.makePaymentFormFromData = (container, payment, on_complete, accepts_header) => {
    if (payment_provider === "WORLDPAY") {
        ReactDOM.render(<WorldpayPayment acceptsHeader={accepts_header} payment={payment}
                                         onComplete={on_complete}/>, container);
    }
};