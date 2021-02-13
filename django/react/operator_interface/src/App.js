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
import Switch from '@material/react-switch';
import ReconnectingWebSocket from './reconnecting-websocket';
import Conversation from './Conversation';

import './App.scss';
import Dialog, {DialogButton, DialogContent, DialogFooter, DialogTitle} from "@material/react-dialog";

export const ROOT_URL = process.env.NODE_ENV === 'production' ?
    "https://" + window.location.host + "/" : "http://localhost:8000/";
export const SockContext = React.createContext(null);


class BookingData {
    constructor(id, data, app) {
        this.id = id;
        this.data = data;
        this.app = app;
    }

    isLoaded() {
        return this.data !== null;
    }

    load() {
        if (!this.isLoaded()) {
            if (this.app.pending_bookings.indexOf(this.id) === -1) {
                this.app.sock.send(JSON.stringify({
                    type: "getBooking",
                    id: this.id
                }));
                this.app.pending_bookings.push(this.id);
            }
            return false;
        }
        return true;
    }

    get time() {
        return this.load() ? new Date(this.data.time) : null;
    }

    get repair() {
        return this.load() ? this.data.repair : null;
    }
}

class PaymentItemData {
    constructor(data) {
        this.data = data;
    }

    get title() {
        return this.data.title;
    }

    get quantity() {
        return this.data.quantity;
    }

    get price() {
        return this.data.price;
    }
}

class PaymentData {
    constructor(id, data, app) {
        this.id = id;
        this.data = data;
        this.app = app;
    }

    isLoaded() {
        return this.data !== null;
    }

    load() {
        if (!this.isLoaded()) {
            if (this.app.pending_payments.indexOf(this.id) === -1) {
                this.app.sock.send(JSON.stringify({
                    type: "getPayment",
                    id: this.id
                }));
                this.app.pending_payments.push(this.id);
            }
            return false;
        }
        return true;
    }

    get items() {
        if (this.load()) {
            let items = [];
            this.data.items.forEach(i => {
                items.push(new PaymentItemData(i));
            });
            return items;
        } else {
            return [];
        }
    }

    get timestamp() {
        return this.load() ? this.data.timestamp : 0;
    }

    get state() {
        return this.load() ? this.data.state : "";
    }

    get payment_method() {
        return this.load() ? this.data.payment_method : "";
    }

    get total() {
        return this.load() ? this.data.total : 0;
    }
}

class MessageData {
    constructor(id, data, app) {
        this.id = id;
        this.data = data;
        this.app = app;
    }

    isLoaded() {
        return this.data !== null;
    }

    load() {
        if (!this.isLoaded()) {
            if (this.app.pending_messages.indexOf(this.id) === -1) {
                this.app.sock.send(JSON.stringify({
                    type: "getMessage",
                    id: this.id
                }));
                this.app.pending_messages.push(this.id);
            }
            return false;
        }
        return true;
    }

    get text() {
        return this.load() ? this.data.text : "";
    }

    get direction() {
        return this.load() ? this.data.direction : "";
    }

    get timestamp() {
        return this.load() ? this.data.timestamp : 0;
    }

    get image() {
        return this.load() ? this.data.image : null;
    }

    get state() {
        return this.load() ? this.data.state : null;
    }

    get end() {
        return this.load() ? this.data.end : false;
    }

    get request_live_agent() {
        return this.load() ? this.data.request_live_agent : false;
    }

    get selection() {
        return this.load() ? (this.data.selection ? JSON.parse(this.data.selection) : null) : false;
    }

    get card() {
        return this.load() ? (this.data.card ? JSON.parse(this.data.card) : null) : false;
    }

    get request() {
        return this.load() ? this.data.request : null;
    }

    get sent_by() {
        return this.load() ? this.data.sent_by : null;
    }

    get payment_request() {
        return this.load() ? (this.data.payment_request ? this.get_payment(this.data.payment_request) : null) : null;
    }

    get payment_confirm() {
        return this.load() ? (this.data.payment_confirm ? this.get_payment(this.data.payment_confirm) : null) : null;
    }

    get platform() {
        return this.data.platform;
    }

    get platform_name() {
        if (this.data.platform === "GA") {
            return "Actions on Google";
        } else if (this.data.platform === "AZ") {
            return "Microsoft Bot Framework";
        } else if (this.data.platform === "TW") {
            return "Twitter";
        } else if (this.data.platform === "FB") {
            return "Facebook";
        } else if (this.data.platform === "TG") {
            return "Telegram";
        } else if (this.data.platform === "TX") {
            return "SMS";
        } else if (this.data.platform === "CH") {
            return "Customer chat";
        } else if (this.data.platform === "AB") {
            return "Apple Business chat";
        } else if (this.data.platform === "EM") {
            return "Email";
        } else if (this.data.platform === "WA") {
            return "WhatsApp";
        } else if (this.data.platform === "AS") {
            const platform_id = this.data.platform_id.split(";", 1)[0];
            if (platform_id === "google-business-messaging") {
                return "Google Business Messaging";
            }
        }
        return "Unknown platform"
    }

    get entities() {
        return this.load() ? this.data.entities.map(e => new MessageEntityData(e)) : [];
    }

    get guessed_intent() {
        return this.load() ? this.data.guessed_intent : null;
    }

    get_payment(p) {
        if (typeof this.app.state.payments[p] === "undefined") {
            return new PaymentData(p, null, this.app);
        } else {
            return this.app.state.payments[p];
        }
    }
}

class MessageEntityData {
    constructor(data) {
        this.data = data;
    }

    get entity() {
        return this.data.entity
    }

    get value() {
        return this.data.value
    }

    get text_value() {
        return JSON.parse(this.value);
    }
}

class ConversationData {
    constructor(id, data, app) {
        this.id = id;
        this.data = data;
        this.app = app;
    }

    get messages() {
        return this.data.messages.map(m => this.get_message(m));
    }

    get payments() {
        return this.data.payments.map(p => this.get_payment(p));
    }

    get bookings() {
        return this.data.repair_bookings.map(b => this.get_booking(b));
    }

    get_message(m) {
        if (typeof this.app.state.messages[m] === "undefined") {
            return new MessageData(m, null, this.app);
        } else {
            return this.app.state.messages[m];
        }
    }

    get_payment(p) {
        if (typeof this.app.state.payments[p] === "undefined") {
            return new PaymentData(p, null, this.app);
        } else {
            return this.app.state.payments[p];
        }
    }

    get_booking(b) {
        if (typeof this.app.state.bookings[b] === "undefined") {
            return new BookingData(b, null, this.app);
        } else {
            return this.app.state.bookings[b];
        }
    }

    get customer_name() {
        return this.data.customer_name ? this.data.customer_name : "Unknown"
    }

    get customer_first_name() {
        return this.data.customer_first_name
    }

    get customer_last_name() {
        return this.data.customer_last_name
    }

    get agent_responding() {
        return this.data.agent_responding
    }

    get current_user_responding() {
        return this.data.current_user_responding
    }

    get user_responding() {
        return this.data.user_responding
    }

    get customer_username() {
        return this.data.customer_username;
    }

    get customer_pic() {
        return this.data.customer_pic;
    }

    get timezone() {
        return this.data.timezone;
    }

    get customer_email() {
        return this.data.customer_email;
    }

    get customer_phone() {
        return this.data.customer_phone;
    }

    get customer_locale() {
        return this.data.customer_locale;
    }

    get customer_gender() {
        return this.data.customer_gender;
    }

    get customer_id() {
        return this.data.customer_id;
    }

    get typing() {
        return this.data.typing;
    }

    can_message() {
        return this.can_interact() && this.current_user_responding && !this.agent_responding
    }

    can_interact() {
        return this.data.can_message;
    }

    send(text) {
        if (this.can_message()) {
            this.app.sock.send(JSON.stringify({
                type: "msg",
                text: text,
                cid: this.id
            }));
        }
    }

    save_entity(entity) {
        this.app.sock.send(JSON.stringify({
            type: "attribute_update",
            cid: this.id,
            attribute: entity.entity,
            value: entity.value
        }))
    }

    typing_on() {
        this.app.sock.send(JSON.stringify({
            type: "typing_on",
            cid: this.id
        }))
    }

    typing_off() {
        this.app.sock.send(JSON.stringify({
            type: "typing_off",
            cid: this.id
        }))
    }
}

class App extends Component {
    constructor(props) {
        super(props);

        this.state = {
            error: null,
            open: true,
            lastMessage: -1,
            conversationOffset: 0,
            selectedCid: null,
            showCustomerPanel: true,
            conversations: {},
            messages: {},
            payments: {},
            bookings: {},
            config: {}
        };

        this.pending_messages = [];
        this.pending_payments = [];
        this.pending_bookings = [];

        this.selectConversation = this.selectConversation.bind(this);
        this.handleOpen = this.handleOpen.bind(this);
        this.handleReceiveMessage = this.handleReceiveMessage.bind(this);
        this.onEnd = this.onEnd.bind(this);
        this.onRequestSignIn = this.onRequestSignIn.bind(this);
        this.onTakeOver = this.onTakeOver.bind(this);
        this.onHandBack = this.onHandBack.bind(this);
        this.convListScroll = this.convListScroll.bind(this);
        this.convList = React.createRef();
    }

    componentDidMount() {
        this.sock = new ReconnectingWebSocket(process.env.NODE_ENV === 'production' ?
            "wss://" + window.location.host + "/ws/operator/" : "ws://localhost:8000/ws/operator/", null, {automaticOpen: false});
        this.sock.onopen = this.handleOpen;
        this.sock.onmessage = this.handleReceiveMessage;
        this.sock.open();
        this.convList.current.addEventListener('scroll', this.convListScroll);
    }

    componentWillUnmount() {
        this.sock.close();
        if (this.convList.current) {
            this.convList.current.removeEventListener('scroll', this.convListScroll);
        }
    }

    convListScroll() {
        let scroll = this.convList.current.scrollHeight - this.convList.current.scrollTop
            - this.convList.current.clientHeight;
        if (scroll === 0) {
            this.state.conversationOffset += 50;
            this.sock.send(JSON.stringify({
                type: "getConversations",
                offset: this.state.conversationOffset
            }));
        }
        console.log(scroll);
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
            messages[data.id] = new MessageData(data.id, data, this);
            let p_index = this.pending_messages.indexOf(data.id);
            if (p_index > -1) {
                this.pending_messages.splice(p_index, 1);
            }
            this.setState({
                messages: messages,
                lastMessage: data.timestamp
            });
        } else if (data.type === "conversation") {
            const conversations = this.state.conversations;
            conversations[data.id] = new ConversationData(data.id, data, this);
            this.setState({
                conversations: conversations
            });
        } else if (data.type === "conversation_delete") {
            const conversations = this.state.conversations;
            let new_cid = this.state.selectedCid;
            if (new_cid === data.id) {
                new_cid = null
            }
            delete conversations[data.id];
            this.setState({
                conversations: conversations,
                selectedCid: new_cid
            });
        } else if (data.type === "conversation_merge") {
            let new_cid = this.state.selectedCid;
            if (new_cid === data.id) {
                new_cid = data.nid;
            }
            this.setState({
                selectedCid: new_cid
            });
        } else if (data.type === "payment") {
            const payments = this.state.payments;
            payments[data.id] = new PaymentData(data.id, data, this);
            let p_index = this.pending_payments.indexOf(data.id);
            if (p_index > -1) {
                this.pending_payments.splice(p_index, 1);
            }
            this.setState({
                payments: payments
            });
        } else if (data.type === "booking") {
            const bookings = this.state.bookings;
            bookings[data.id] = new BookingData(data.id, data, this);
            let p_index = this.pending_bookings.indexOf(data.id);
            if (p_index > -1) {
                this.pending_bookings.splice(p_index, 1);
            }
            this.setState({
                bookings: bookings
            });
        } else if (data.type === "error") {
            this.setState({
                error: data.msg
            });
        } else if (data.type === "config") {
            this.setState({
                config: data.config
            });
        }
    }

    handleOpen() {
        if (this.state.lastMessage === -1) {
            this.sock.send(JSON.stringify({
                type: "getConversations",
                offset: this.state.conversationOffset
            }));
        } else {
            this.sock.send(JSON.stringify({
                type: "resyncReq",
                lastMessage: this.state.lastMessage
            }));
        }

        this.pending_messages.forEach(m => {
            this.sock.send(JSON.stringify({
                type: "getMessage",
                id: m
            }));
        });
        this.pending_payments.forEach(p => {
            this.sock.send(JSON.stringify({
                type: "getPayment",
                id: p
            }));
        });
        this.pending_bookings.forEach(b => {
            this.sock.send(JSON.stringify({
                type: "getBooking",
                id: b
            }));
        });
    }

    onEnd() {
        this.sock.send(JSON.stringify({
            type: "endConv",
            cid: this.state.selectedCid
        }));
    }

    onRequestSignIn() {
        this.sock.send(JSON.stringify({
            type: "request_sign_in",
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

    render() {
        const conversations = Object.values(this.state.conversations)
            .map(c => {
                let msgs = c.messages;

                let lastMsg = null;
                if (msgs.length === 0) {
                    lastMsg = new MessageData(null, {text: "No messages"}, this);
                } else {
                    let i = 1;
                    lastMsg = msgs[msgs.length - i];
                        while (!lastMsg.isLoaded()) {
                            i++;
                            if (i >= msgs.length) {
                                break;
                            }
                            lastMsg = msgs[msgs.length - i];
                        }
                        if (!lastMsg.isLoaded()) {
                            i = 1;
                            lastMsg = msgs[msgs.length - i];
                            if (lastMsg) {
                                lastMsg.load();
                            }
                        }
                        while (lastMsg && lastMsg.isLoaded()) {
                            if (lastMsg.text) {
                                break;
                            }
                            i++;
                            if (i >= msgs.length) {
                                break;
                            }
                            lastMsg = msgs[msgs.length - i];
                            if (lastMsg) {
                                 lastMsg.load();
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

                    <div className="mdc-drawer__content" ref={this.convList}>
                        <List twoLine avatarList singleSelection
                              selectedIndex={this.state.selectedCid === null ? null :
                                  conversations.map((c, i) => ({c: c, i: i}))
                                      .filter(c => c.c.c.id === this.state.selectedCid)[0].i}>
                            {conversations.map(c => {
                                return <ListItem key={c.c.id} onClick={() => this.selectConversation(c.c.id)}>
                                    <ListItemGraphic graphic={<img src={c.c.customer_pic} alt=""/>}/>
                                    <ListItemText
                                        primaryText={c.c.customer_name}
                                        secondaryText={(c.lastMsg.direction === "O" ? "Them: " : "You: ") + c.lastMsg.text}/>
                                    {!(c.c.agent_responding || c.c.user_responding) ?
                                        <ListItemMeta meta={<MaterialIcon icon='notification_important'/>}/> : null}
                                </ListItem>
                            })}
                        </List>
                    </div>
                </Drawer>

                <DrawerAppContent className='drawer-app-content'>
                    <Dialog
                        onClose={() => this.setState({error: null})}
                        open={!!this.state.error}>
                        <DialogTitle>An error occurred</DialogTitle>
                        <DialogContent>
                            {this.state.error}
                        </DialogContent>
                        <DialogFooter>
                            <DialogButton action='dismiss' isDefault>Ok</DialogButton>
                        </DialogFooter>
                    </Dialog>
                    <TopAppBar>
                        <TopAppBarRow>
                            <TopAppBarSection align='start'>
                                <TopAppBarIcon navIcon>
                                    <MaterialIcon icon='menu' onClick={() => this.setState({open: !this.state.open})}/>
                                </TopAppBarIcon>
                                <TopAppBarTitle>{this.state.selectedCid === null ? "Loading..." :
                                    this.state.conversations[this.state.selectedCid].customer_name}</TopAppBarTitle>
                            </TopAppBarSection>
                            <TopAppBarSection role='toolbar' className="top-bar">
                                {this.state.selectedCid === null ||
                                !this.state.conversations[this.state.selectedCid].can_interact() ? null :
                                    <React.Fragment>
                                        {!this.state.conversations[this.state.selectedCid].agent_responding ?
                                            <React.Fragment>
                                                {/*<Button raised onClick={this.onHandBack}>*/}
                                                {/*    Hand back to bot*/}
                                                {/*</Button>*/}
                                                {!this.state.conversations[this.state.selectedCid]
                                                    .current_user_responding ?
                                                    <Button raised onClick={this.onTakeOver}>
                                                        Take over
                                                    </Button> : <React.Fragment>
                                                        <Button raised onClick={this.onEnd}>
                                                            End conversation
                                                        </Button>
                                                        {!this.state.conversations[this.state.selectedCid].customer_id ?
                                                            <Button raised onClick={this.onRequestSignIn}>
                                                                Request sign in
                                                            </Button> : null}
                                                    </React.Fragment>
                                                }
                                            </React.Fragment> :
                                            <Button raised onClick={this.onTakeOver}>
                                                Take over from bot
                                            </Button>
                                        }
                                        Signed in as {this.state.config.user_name}
                                        <Button ripple colored raised href="/auth/logout">Logout</Button>
                                        <Switch
                                            nativeControlId="customer-panel-switch"
                                            checked={this.state.showCustomerPanel}
                                            onChange={e => this.setState({showCustomerPanel: e.target.checked})}/>
                                        <label htmlFor="customer-panel-switch">Customer Panel</label>
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
                                    conversation={this.state.conversations[this.state.selectedCid]}
                                    showCustomerPanel={this.state.showCustomerPanel}
                                    onError={e => this.setState({
                                        error: e
                                    })}
                                />
                            </SockContext.Provider>}
                    </TopAppBarFixedAdjust>
                </DrawerAppContent>
            </div>
        );
    }
}

export default App;
