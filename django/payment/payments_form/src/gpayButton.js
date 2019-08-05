import React, { Component } from 'react';

export default class GPayButton extends Component {
    componentDidMount() {
        const button = this.props.paymentsClient.createButton({
            onClick: this.props.onClick,
            buttonColor: "dark",
            buttonType: "long"
        });
        const elm = this.refs.button;
        elm.parentNode.replaceChild(button, elm);
    }

    render() {
        return <div ref="button"/>
    }
}