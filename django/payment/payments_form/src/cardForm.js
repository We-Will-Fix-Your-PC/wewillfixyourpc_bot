import React, {Component} from 'react';
import {FontAwesomeIcon} from '@fortawesome/react-fontawesome'
import {faCcVisa, faCcMastercard, faCcAmex} from '@fortawesome/free-brands-svg-icons'
import Payment from 'payment';

export default class CardForm extends Component {
    constructor(props) {
        super(props);

        this.state = {
            card_type: null
        };

        this.setCardType = this.setCardType.bind(this);
        this.handleSubmit = this.handleSubmit.bind(this);
    }

    renderCardList() {
        return <div className="card-list">
            <FontAwesomeIcon icon={faCcVisa} size="3x"
                             className={this.state.card_type === "visa" ? "active" : ""}/>
            <FontAwesomeIcon icon={faCcAmex} size="3x"
                             className={this.state.card_type === "amex" ? "active" : ""}/>
            <FontAwesomeIcon icon={faCcMastercard} size="3x"
                             className={this.state.card_type === "mastercard" ? "active" : ""}/>
        </div>;
    }

    componentDidMount() {
        const {number, cvc} = this.refs;
        Payment.formatCardNumber(number);
        Payment.formatCardCVC(cvc);
    }

    setCardType(event) {
        const type = Payment.fns.cardType(event.target.value);
        this.setState({
            card_type: type
        })
    }

    handleSubmit(event) {
        event.preventDefault();

        const {refs} = this;
        const name = refs.name.value;
        const number = refs.number.value;
        const exp_month = parseInt(refs.month.value, 10);
        const exp_year = parseInt(refs.year.value, 10);
        const cvc = refs.cvc.value;
        const paymentResponse = {
            details: {
                billingAddress: {
                    addressLine: [],
                    country: "",
                    city: "",
                    dependentLocality: "",
                    organization: "",
                    phone: refs.phone ? refs.phone.value : this.props.payment.customer.phone,
                    postalCode: "",
                    recipient: refs.name.value,
                    region: "",
                    regionCode: "",
                    sortingCode: ""
                },
                cardNumber: number,
                cardholderName: name,
                cardSecurityCode: cvc,
                expiryMonth: exp_month,
                expiryYear: exp_year
            },
            methodName: "basic-card",
            payerName: name,
            complete: () => Promise.resolve({})
        };
        if (this.props.paymentOptions.requestPayerPhone) {
            paymentResponse.payerPhone = refs.phone ? refs.phone.value : this.props.payment.customer.phone;
        }
        if (this.props.paymentOptions.requestPayerEmail) {
            paymentResponse.payerEmail = refs.email.value;
        }
        this.props.onSubmit(paymentResponse);
    }

    render() {
        let curYear = new Date().getFullYear();
        let hasPhone = false;
        if (this.props.payment.customer) {
            if (this.props.payment.customer.phone) {
                hasPhone = true;
            }
        }
        return <div className="CardForm">
            {this.renderCardList()}
            <form onSubmit={this.handleSubmit}>
                <input className="card-name" type="text" ref="name" placeholder="Name on card" required/>
                <input className="card-number" type="text" ref="number" placeholder="Card number" required
                       pattern="[0-9 ]*" onKeyUp={this.setCardType}/>
                <select className="exp-month" ref="month" required>
                    <option value="">Exp month</option>
                    {[...Array(12).keys()].map(i => <option key={i} value={i + 1}>{i + 1}</option>)}
                </select>
                <select className="exp-year" ref="year" required>
                    <option value="">Exp year</option>
                    {[...Array(10).keys()].map(i => <option key={i} value={i + curYear}>{i + curYear}</option>)}
                </select>
                <input className="cvc" type="text" ref="cvc" placeholder="CVC" maxLength={4} required
                       pattern="[0-9]*"/>
                {(!hasPhone) ?
                    <input className="phone" type="tel" ref="phone" placeholder="Phone number" required/> : null}
                {(this.props.paymentOptions.requestPayerEmail) ?
                    <input className="email" type="email" ref="email" placeholder="Email address" required/> : null}
                <button type="submit">Submit</button>
            </form>
        </div>;
    }
}