import React, {Component} from 'react';
import Tab from '@material/react-tab';
import TabBar from '@material/react-tab-bar';
import List, {ListItem, ListItemText} from '@material/react-list';
import Card from '@material/react-card';
import dateformat from "dateformat";
import OrderCard from "./OrderCard";

export default class CustomerPanel extends Component {
    state = {activeTab: 0};

    render() {
        let orderStates = {
            "O": "Open",
            "P": "Paid",
            "C": "Complete",
        };

        // console.log(this.props.conversation.payments);

        return <React.Fragment>
            <img src={this.props.conversation.customer_pic} alt="" className="profile"/>
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
                    <span>{this.props.conversation.customer_username ? this.props.conversation.customer_username : "N/A"}</span>
                    <span>Bot responding:</span>
                    <span>{this.props.conversation.agent_responding ? "Yes" : "No"}</span>
                    <span>Timezone:</span>
                    <span>{this.props.conversation.timezone ? this.props.conversation.timezone : "N/A"}</span>
                    <span>Email:</span>
                    <span>{this.props.conversation.customer_email ? this.props.conversation.customer_email : "N/A"}</span>
                    <span>Phone:</span>
                    <span>{this.props.conversation.customer_phone ? this.props.conversation.customer_phone : "N/A"}</span>
                    <span>Locale:</span>
                    <span>{this.props.conversation.customer_locale ? this.props.conversation.customer_locale : "N/A"}</span>
                    <span>Gender:</span>
                    <span>{this.props.conversation.customer_gender ? this.props.conversation.customer_gender : "N/A"}</span>
                </div> : null
            }
            {this.state.activeTab === 1 ?
                <div className="ordering">
                    <h3>Current order</h3>
                    <OrderCard conversation={this.props.conversation}/>
                    <h3>Order History</h3>
                    <div className="orderHistory">
                        {this.props.conversation.payments.map(p => {
                            let d = new Date(0);
                            d.setUTCSeconds(p.timestamp);

                            return <Card key={p.id} className="order" outlined>
                                <span>ID:</span>
                                <span>{p.id}</span>
                                <span>State:</span>
                                <span>{orderStates[p.state]}</span>
                                <span>Time:</span>
                                <span>{dateformat(d, "h:MM TT ddd mmm dS yyyy")}</span>
                                <span>Payment method:</span>
                                <span>{p.payment_method}</span>
                                <span>Total:</span>
                                <span>{p.total} GBP</span>
                                <div className="items">
                                    <h4>Items</h4>
                                    <List twoLine>
                                        {p.items.map(i => {
                                            return <ListItem key={i.id}>
                                                <ListItemText primaryText={i.title}
                                                              secondaryText={`${i.quantity} @ ${i.price} GBP`}/>
                                            </ListItem>
                                        })}
                                    </List>
                                </div>
                            </Card>
                        })}
                    </div>
                </div> : null
            }

        </React.Fragment>
    }
}