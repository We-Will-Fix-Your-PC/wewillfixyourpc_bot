import React, {Component} from 'react';
import Tab from '@material/react-tab';
import TabBar from '@material/react-tab-bar';
import dateformat from "dateformat";

export default class CustomerPanel extends Component {
    state = {activeTab: 0};

    render() {
        let orderStates = {
            "O": "Open",
            "P": "Paid",
            "C": "Complete",
        };

        return <React.Fragment>
            <img src={this.props.conversation.picture} alt="" className="profile"/>
            <TabBar
                activeIndex={this.state.activeTab}
                handleActiveIndexUpdate={i => this.setState({activeTab: i})}
            >
                <Tab>
                    <span className='mdc-tab__text-label'>Info</span>
                </Tab>
                <Tab>
                    <span className='mdc-tab__text-label'>Ordering</span>
                </Tab>
            </TabBar>
            {this.state.activeTab === 0 ?
                <div className="custInfo">
                    <span>Name:</span>
                    <span>{this.props.conversation.customer_name}</span>
                    <span>Username:</span>
                    <span>{this.props.conversation.username ? this.props.conversation.username : "N/A"}</span>
                    <span>Bot responding:</span>
                    <span>{this.props.conversation.agent_responding ? "Yes" : "No"}</span>
                    <span>Timezone:</span>
                    <span>{this.props.conversation.timezone ? this.props.conversation.timezone : "N/A"}</span>
                    <span>Email:</span>
                    <span>{this.props.conversation.customer_email ? this.props.conversation.customer_email : "N/A"}</span>
                    <span>Phone:</span>
                    <span>{this.props.conversation.customer_phone ? this.props.conversation.customer_phone : "N/A"}</span>
                </div> : null
            }
            {this.state.activeTab === 1 ?
                <div className="ordering">
                    <h3>Order History</h3>
                    <div className="orderHistory">
                        {this.props.conversation.payments.map(p => {
                            let d = new Date(0);
                            d.setUTCSeconds(p.timestamp);

                            return <div className="order">
                                <span>ID:</span>
                                <span>{p.id}</span>
                                <span>State:</span>
                                <span>{orderStates[p.state]}</span>
                                <span>Time:</span>
                                <span>{dateformat(d, "h:MM TT ddd mmm dS yyyy")}</span>
                                <span>Payment method:</span>
                                <span>{p.payment_method}</span>
                                <span>Total:</span>
                                <span>{p.total}</span>
                                <div className="items">
                                    <h4>Items</h4>
                                    {p.items.map(i => {
                                        return <div className="item">
                                            <span>{i.quantity}x</span>
                                            <span>{i.title}</span>
                                            <span>@{i.price}</span>
                                        </div>
                                    })}
                                </div>
                            </div>
                        })}
                    </div>
                </div> : null
            }

        </React.Fragment>
    }
}