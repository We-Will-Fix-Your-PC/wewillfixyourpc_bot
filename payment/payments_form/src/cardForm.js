import React, {Component} from 'react';
import {FontAwesomeIcon} from '@fortawesome/react-fontawesome'
import {faCcVisa, faCcMastercard, faCcAmex, faCcJcb, faCcDinersClub} from '@fortawesome/free-brands-svg-icons'
import Payment from 'payment';

const isoCountries = {
    'AF' : 'Afghanistan',
    'AX' : 'Aland Islands',
    'AL' : 'Albania',
    'DZ' : 'Algeria',
    'AS' : 'American Samoa',
    'AD' : 'Andorra',
    'AO' : 'Angola',
    'AI' : 'Anguilla',
    'AQ' : 'Antarctica',
    'AG' : 'Antigua And Barbuda',
    'AR' : 'Argentina',
    'AM' : 'Armenia',
    'AW' : 'Aruba',
    'AU' : 'Australia',
    'AT' : 'Austria',
    'AZ' : 'Azerbaijan',
    'BS' : 'Bahamas',
    'BH' : 'Bahrain',
    'BD' : 'Bangladesh',
    'BB' : 'Barbados',
    'BY' : 'Belarus',
    'BE' : 'Belgium',
    'BZ' : 'Belize',
    'BJ' : 'Benin',
    'BM' : 'Bermuda',
    'BT' : 'Bhutan',
    'BO' : 'Bolivia',
    'BA' : 'Bosnia And Herzegovina',
    'BW' : 'Botswana',
    'BV' : 'Bouvet Island',
    'BR' : 'Brazil',
    'IO' : 'British Indian Ocean Territory',
    'BN' : 'Brunei Darussalam',
    'BG' : 'Bulgaria',
    'BF' : 'Burkina Faso',
    'BI' : 'Burundi',
    'KH' : 'Cambodia',
    'CM' : 'Cameroon',
    'CA' : 'Canada',
    'CV' : 'Cape Verde',
    'KY' : 'Cayman Islands',
    'CF' : 'Central African Republic',
    'TD' : 'Chad',
    'CL' : 'Chile',
    'CN' : 'China',
    'CX' : 'Christmas Island',
    'CC' : 'Cocos (Keeling) Islands',
    'CO' : 'Colombia',
    'KM' : 'Comoros',
    'CG' : 'Congo',
    'CD' : 'Congo, Democratic Republic',
    'CK' : 'Cook Islands',
    'CR' : 'Costa Rica',
    'CI' : 'Cote D\'Ivoire',
    'HR' : 'Croatia',
    'CU' : 'Cuba',
    'CY' : 'Cyprus',
    'CZ' : 'Czech Republic',
    'DK' : 'Denmark',
    'DJ' : 'Djibouti',
    'DM' : 'Dominica',
    'DO' : 'Dominican Republic',
    'EC' : 'Ecuador',
    'EG' : 'Egypt',
    'SV' : 'El Salvador',
    'GQ' : 'Equatorial Guinea',
    'ER' : 'Eritrea',
    'EE' : 'Estonia',
    'ET' : 'Ethiopia',
    'FK' : 'Falkland Islands (Malvinas)',
    'FO' : 'Faroe Islands',
    'FJ' : 'Fiji',
    'FI' : 'Finland',
    'FR' : 'France',
    'GF' : 'French Guiana',
    'PF' : 'French Polynesia',
    'TF' : 'French Southern Territories',
    'GA' : 'Gabon',
    'GM' : 'Gambia',
    'GE' : 'Georgia',
    'DE' : 'Germany',
    'GH' : 'Ghana',
    'GI' : 'Gibraltar',
    'GR' : 'Greece',
    'GL' : 'Greenland',
    'GD' : 'Grenada',
    'GP' : 'Guadeloupe',
    'GU' : 'Guam',
    'GT' : 'Guatemala',
    'GG' : 'Guernsey',
    'GN' : 'Guinea',
    'GW' : 'Guinea-Bissau',
    'GY' : 'Guyana',
    'HT' : 'Haiti',
    'HM' : 'Heard Island & Mcdonald Islands',
    'VA' : 'Holy See (Vatican City State)',
    'HN' : 'Honduras',
    'HK' : 'Hong Kong',
    'HU' : 'Hungary',
    'IS' : 'Iceland',
    'IN' : 'India',
    'ID' : 'Indonesia',
    'IR' : 'Iran, Islamic Republic Of',
    'IQ' : 'Iraq',
    'IE' : 'Ireland',
    'IM' : 'Isle Of Man',
    'IL' : 'Israel',
    'IT' : 'Italy',
    'JM' : 'Jamaica',
    'JP' : 'Japan',
    'JE' : 'Jersey',
    'JO' : 'Jordan',
    'KZ' : 'Kazakhstan',
    'KE' : 'Kenya',
    'KI' : 'Kiribati',
    'KR' : 'Korea',
    'KW' : 'Kuwait',
    'KG' : 'Kyrgyzstan',
    'LA' : 'Lao People\'s Democratic Republic',
    'LV' : 'Latvia',
    'LB' : 'Lebanon',
    'LS' : 'Lesotho',
    'LR' : 'Liberia',
    'LY' : 'Libyan Arab Jamahiriya',
    'LI' : 'Liechtenstein',
    'LT' : 'Lithuania',
    'LU' : 'Luxembourg',
    'MO' : 'Macao',
    'MK' : 'Macedonia',
    'MG' : 'Madagascar',
    'MW' : 'Malawi',
    'MY' : 'Malaysia',
    'MV' : 'Maldives',
    'ML' : 'Mali',
    'MT' : 'Malta',
    'MH' : 'Marshall Islands',
    'MQ' : 'Martinique',
    'MR' : 'Mauritania',
    'MU' : 'Mauritius',
    'YT' : 'Mayotte',
    'MX' : 'Mexico',
    'FM' : 'Micronesia, Federated States Of',
    'MD' : 'Moldova',
    'MC' : 'Monaco',
    'MN' : 'Mongolia',
    'ME' : 'Montenegro',
    'MS' : 'Montserrat',
    'MA' : 'Morocco',
    'MZ' : 'Mozambique',
    'MM' : 'Myanmar',
    'NA' : 'Namibia',
    'NR' : 'Nauru',
    'NP' : 'Nepal',
    'NL' : 'Netherlands',
    'AN' : 'Netherlands Antilles',
    'NC' : 'New Caledonia',
    'NZ' : 'New Zealand',
    'NI' : 'Nicaragua',
    'NE' : 'Niger',
    'NG' : 'Nigeria',
    'NU' : 'Niue',
    'NF' : 'Norfolk Island',
    'MP' : 'Northern Mariana Islands',
    'NO' : 'Norway',
    'OM' : 'Oman',
    'PK' : 'Pakistan',
    'PW' : 'Palau',
    'PS' : 'Palestinian Territory, Occupied',
    'PA' : 'Panama',
    'PG' : 'Papua New Guinea',
    'PY' : 'Paraguay',
    'PE' : 'Peru',
    'PH' : 'Philippines',
    'PN' : 'Pitcairn',
    'PL' : 'Poland',
    'PT' : 'Portugal',
    'PR' : 'Puerto Rico',
    'QA' : 'Qatar',
    'RE' : 'Reunion',
    'RO' : 'Romania',
    'RU' : 'Russian Federation',
    'RW' : 'Rwanda',
    'BL' : 'Saint Barthelemy',
    'SH' : 'Saint Helena',
    'KN' : 'Saint Kitts And Nevis',
    'LC' : 'Saint Lucia',
    'MF' : 'Saint Martin',
    'PM' : 'Saint Pierre And Miquelon',
    'VC' : 'Saint Vincent And Grenadines',
    'WS' : 'Samoa',
    'SM' : 'San Marino',
    'ST' : 'Sao Tome And Principe',
    'SA' : 'Saudi Arabia',
    'SN' : 'Senegal',
    'RS' : 'Serbia',
    'SC' : 'Seychelles',
    'SL' : 'Sierra Leone',
    'SG' : 'Singapore',
    'SK' : 'Slovakia',
    'SI' : 'Slovenia',
    'SB' : 'Solomon Islands',
    'SO' : 'Somalia',
    'ZA' : 'South Africa',
    'GS' : 'South Georgia And Sandwich Isl.',
    'ES' : 'Spain',
    'LK' : 'Sri Lanka',
    'SD' : 'Sudan',
    'SR' : 'Suriname',
    'SJ' : 'Svalbard And Jan Mayen',
    'SZ' : 'Swaziland',
    'SE' : 'Sweden',
    'CH' : 'Switzerland',
    'SY' : 'Syrian Arab Republic',
    'TW' : 'Taiwan',
    'TJ' : 'Tajikistan',
    'TZ' : 'Tanzania',
    'TH' : 'Thailand',
    'TL' : 'Timor-Leste',
    'TG' : 'Togo',
    'TK' : 'Tokelau',
    'TO' : 'Tonga',
    'TT' : 'Trinidad And Tobago',
    'TN' : 'Tunisia',
    'TR' : 'Turkey',
    'TM' : 'Turkmenistan',
    'TC' : 'Turks And Caicos Islands',
    'TV' : 'Tuvalu',
    'UG' : 'Uganda',
    'UA' : 'Ukraine',
    'AE' : 'United Arab Emirates',
    'GB' : 'United Kingdom',
    'US' : 'United States',
    'UM' : 'United States Outlying Islands',
    'UY' : 'Uruguay',
    'UZ' : 'Uzbekistan',
    'VU' : 'Vanuatu',
    'VE' : 'Venezuela',
    'VN' : 'Viet Nam',
    'VG' : 'Virgin Islands, British',
    'VI' : 'Virgin Islands, U.S.',
    'WF' : 'Wallis And Futuna',
    'EH' : 'Western Sahara',
    'YE' : 'Yemen',
    'ZM' : 'Zambia',
    'ZW' : 'Zimbabwe'
};

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
            <FontAwesomeIcon icon={faCcJcb} size="3x"
                             className={this.state.card_type === "jcb" ? "active" : ""}/>
            <FontAwesomeIcon icon={faCcDinersClub} size="3x"
                             className={this.state.card_type === "dinersclub" ? "active" : ""}/>
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
                    <option value="">Exp. month</option>
                    {[...Array(12).keys()].map(i => <option key={i} value={i + 1}>{i + 1}</option>)}
                </select>
                <select className="exp-year" ref="year" required>
                    <option value="">Exp. year</option>
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