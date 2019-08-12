import React, {Component} from 'react';
import TopAppBar, {
    TopAppBarFixedAdjust,
    TopAppBarIcon,
    TopAppBarRow,
    TopAppBarSection,
    TopAppBarTitle
} from '@material/react-top-app-bar';
import Drawer, {DrawerAppContent, DrawerContent, DrawerHeader, DrawerTitle,} from '@material/react-drawer';
import MaterialIcon from '@material/react-material-icon';
import List, {ListItem, ListItemGraphic, ListItemMeta, ListItemText} from '@material/react-list';
import Button from '@material/react-button';
import ReconnectingWebSocket from './reconnecting-websocket';
import Conversation from './Conversation';

import './App.scss';

export const ROOT_URL = process.env.NODE_ENV === 'production' ?
    "https://" + window.location.host + "/" : "http://localhost:8000/";
export const SockContext = React.createContext(null);

class App extends Component {
    constructor(props) {
        super(props);

        this.state = {
            open: true,
            lastMessage: 0,
            selectedCid: null,
            conversations: {},
            messages: {},
            payments: {},
            paymentItems: {},
        };

        this.getConversation = this.getConversation.bind(this);
        this.getConversationMessages = this.getConversationMessages.bind(this);
        this.getConversationPayments = this.getConversationPayments.bind(this);
        this.getPayment = this.getPayment.bind(this);

        this.selectConversation = this.selectConversation.bind(this);
        this.handleOpen = this.handleOpen.bind(this);
        this.handleReceiveMessage = this.handleReceiveMessage.bind(this);
        this.onSend = this.onSend.bind(this);
        this.onEnd = this.onEnd.bind(this);
        this.onTakeOver = this.onTakeOver.bind(this);
        this.onHandBack = this.onHandBack.bind(this);
    }

    componentDidMount() {
        this.sock = new ReconnectingWebSocket(process.env.NODE_ENV === 'production' ?
            "wss://" + window.location.host + "/ws/operator/" : "ws://localhost:8000/ws/operator/", null, {automaticOpen: false});
        this.sock.onopen = this.handleOpen;
        this.sock.onmessage = this.handleReceiveMessage;
        this.sock.open();
    }

    componentWillUnmount() {
        this.sock.close();
    }

    selectConversation(i) {
        this.setState({
            selectedCid: i
        })
    }

    handleReceiveMessage(msg) {
        const data = JSON.parse(msg.data);

        if (data.type === "message") {
            const messages = this.state.messages;
            messages[data.id] = data;
            this.setState({
                messages: messages,
                lastMessage: data.timestamp
            });
            if (!this.state.conversations[data.conversation_id]) {
                this.sock.send(JSON.stringify({
                    type: "getConversation",
                    id: data.conversation_id
                }));
            }
            if (data.payment_request) {
                if (!this.state.payments[data.payment_request]) {
                    this.sock.send(JSON.stringify({
                        type: "getPayment",
                        id: data.payment_request
                    }));
                }
            }
            if (data.payment_confirm) {
                if (!this.state.payments[data.payment_confirm]) {
                    this.sock.send(JSON.stringify({
                        type: "getPayment",
                        id: data.payment_confirm
                    }));
                }
            }
        } else if (data.type === "conversation") {
            const conversations = this.state.conversations;
            conversations[data.id] = data;
            this.setState({
                conversations: conversations
            });
        } else if (data.type === "payment") {
            const payments = this.state.payments;
            payments[data.id] = data;
            this.setState({
                payments: payments
            });
            for (let item of data.items) {
                if (!this.state.paymentItems[item]) {
                    this.sock.send(JSON.stringify({
                        type: "getPaymentItem",
                        id: item
                    }));
                }
            }
        } else if (data.type === "payment_item") {
            const paymentItems = this.state.paymentItems;
            paymentItems[data.id] = data;
            this.setState({
                paymentItems: paymentItems
            });
        }
    }

    handleOpen() {
        this.sock.send(JSON.stringify({
            type: "resyncReq",
            lastMessage: this.state.lastMessage
        }));
    }

    onSend(text) {
        this.sock.send(JSON.stringify({
            type: "msg",
            text: text,
            cid: this.state.selectedCid
        }));
    }

    onEnd() {
        this.sock.send(JSON.stringify({
            type: "endConv",
            cid: this.state.selectedCid
        }));
    }

    onTakeOver() {
        this.sock.send(JSON.stringify({
            type: "takeOver",
            cid: this.state.selectedCid
        }));
    }

    onHandBack() {
        this.sock.send(JSON.stringify({
            type: "finishConv",
            cid: this.state.selectedCid
        }));
    }

    getConversationMessages(cid) {
        let msgs = Object.entries(this.state.messages)
            .filter(([mid, m]) => m.conversation_id.toString() === cid.toString())
            .map(([mid, m]) => m);
        msgs.sort((f, s) => f.timestamp - s.timestamp);
        return msgs;
    }

    getConversationPayments(msgs) {
        let payments = msgs.map(m => {
            if (m.payment_request) {
                return this.getPayment(m.payment_request);
            } else if (m.payment_confirm) {
                return this.getPayment(m.payment_confirm);
            } else {
                return null;
            }
        }).filter(p => p !== null);
        let seen_payments = [];
        let unique_payments = payments.filter(p => {
            if (seen_payments.indexOf(p.id) !== -1) {
                return false;
            } else {
                seen_payments.push(p.id);
                return true;
            }
        });
        unique_payments.sort((f, s) => s.timestamp - f.timestamp);
        return unique_payments;
    }

    getPayment(pid) {
        let payment = Object.assign({}, this.state.payments[pid]);
        payment = Object.assign(payment, {
            items: Object.entries(this.state.paymentItems).filter(([_, pi]) => pi.payment_id === pid)
                .map(([_, pi]) => pi)
        });
        return payment;
    }

    getConversation(cid) {
        let msgs = this.getConversationMessages(cid);
        let conversation = Object.assign({}, this.state.conversations[cid]);
        return Object.assign(conversation, {
            messages: msgs,
            payments: this.getConversationPayments(msgs),
        });
    }

    render() {
        const conversations = Object.entries(this.state.conversations)
            .map(([cid, c]) => {
                let msgs = this.getConversationMessages(cid);
                let i = 1;
                let lastMsg = msgs[msgs.length - i];
                if (typeof lastMsg === "undefined") {
                    lastMsg = {text: "No messages"};
                } else {
                    while (!lastMsg.text) {
                        i++;
                        lastMsg = msgs[msgs.length - i];
                        if (typeof lastMsg === "undefined") {
                            lastMsg = {text: "No messages"};
                        }
                    }
                }

                return {c: c, lastMsg: lastMsg}
            })
            .sort((f, s) => s.lastMsg.timestamp - f.lastMsg.timestamp);

        return (
            <div className='drawer-container'>
                <Drawer dismissible open={this.state.open}>
                    <DrawerHeader>
                        <DrawerTitle tag='h2'>
                            Agent interface
                        </DrawerTitle>
                    </DrawerHeader>

                    <DrawerContent>
                        <List twoLine avatarList singleSelection
                              selectedIndex={this.state.selectedCid === null ? null :
                                  conversations.map((c, i) => ({c: c, i: i}))
                                      .filter(c => c.c.c.id === this.state.selectedCid)[0].i}>
                            {conversations.map(c => {
                                return <ListItem key={c.c.id} onClick={() => this.selectConversation(c.c.id)}>
                                    <ListItemGraphic graphic={<img src={c.c.customer_pic} alt=""/>}/>
                                    <ListItemText
                                        primaryText={c.c.customer_name}
                                        secondaryText={c.lastMsg.text}/>
                                    {!c.c.agent_responding ?
                                        <ListItemMeta meta={<MaterialIcon icon='notification_important'/>}/> : null}
                                </ListItem>
                            })}
                        </List>
                    </DrawerContent>
                </Drawer>

                <DrawerAppContent className='drawer-app-content'>
                    <TopAppBar>
                        <TopAppBarRow>
                            <TopAppBarSection align='start'>
                                <TopAppBarIcon navIcon>
                                    <MaterialIcon icon='menu' onClick={() => this.setState({open: !this.state.open})}/>
                                </TopAppBarIcon>
                                <TopAppBarTitle>{this.state.selectedCid === null ? "Loading..." :
                                    this.state.conversations[this.state.selectedCid.toString()].customer_name}</TopAppBarTitle>
                            </TopAppBarSection>
                            <TopAppBarSection role='toolbar'>
                                {this.state.selectedCid === null ? null :
                                    <React.Fragment>
                                        <Button raised onClick={this.onEnd}>
                                            End conversation
                                        </Button>
                                        {!this.state.conversations[this.state.selectedCid.toString()].agent_responding ?
                                            <React.Fragment>
                                                <Button raised onClick={this.onHandBack}>
                                                    Hand back to bot
                                                </Button>
                                                {!this.state.conversations[this.state.selectedCid.toString()]
                                                    .current_user_responding ?
                                                    <Button raised onClick={this.onTakeOver}>
                                                        Take over
                                                    </Button> : null
                                                }
                                            </React.Fragment> :
                                            <Button raised onClick={this.onTakeOver}>
                                                Take over from bot
                                            </Button>
                                        }
                                    </React.Fragment>
                                }
                            </TopAppBarSection>
                        </TopAppBarRow>
                    </TopAppBar>

                    <TopAppBarFixedAdjust>
                        {this.state.selectedCid === null ?
                            <h2>Please select a conversation from the drawer</h2> :
                            <SockContext.Provider value={this.sock}>
                                <Conversation
                                    conversation={this.getConversation(this.state.selectedCid)}
                                    onSend={this.onSend}
                                />
                            </SockContext.Provider>}
                    </TopAppBarFixedAdjust>
                </DrawerAppContent>
            </div>
        );
    }
}

export default App;
