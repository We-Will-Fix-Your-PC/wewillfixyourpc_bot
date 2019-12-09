import React, {Component} from 'react';
import Select, {Option} from "@material/react-select";
import {ROOT_URL, SockContext} from "./App";
import Dialog, {DialogButton, DialogContent, DialogFooter, DialogTitle} from "@material/react-dialog";
import TextField, {Input} from "@material/react-text-field";
import Button from "@material/react-button";

class RepairBooking extends Component {
    state = {
        date: '',
        time: '',
        dateValid: null,
        timeValid: null,
        isOpen: null
    };

    date_regex = /^(\d{4})[/-](\d{2})[/-](\d{2})$/;
    time_regex = /^(\d{2}):(\d{2})$/;

    constructor(props) {
        super(props);

        this.dialogClose = this.dialogClose.bind(this);
        this.updateDate = this.updateDate.bind(this);
        this.updateTime = this.updateTime.bind(this);
    }

    updateDate(e) {
        let date = e.target.value;
        let valid = date.match(this.date_regex) !== null;

        this.setState({
            date: date,
            dateValid: valid
        });
        this.getOpen(date, valid, this.state.time, this.state.timeValid);
    }

    updateTime(e) {
        let time= e.target.value;
        let valid = time.match(this.time_regex) !== null;

        this.setState({
            time: time,
            timeValid: valid
        });
        this.getOpen(this.state.date, this.state.dateValid, time, valid);
    }

     getOpen(date, dateValid, time, timeValid) {
        if (dateValid && timeValid) {
            fetch(ROOT_URL + `data/open/?time=${date}T${time}Z`, {
                credentials: "include"
            })
                .then(r => r.json())
                .then(r => {
                    this.setState({
                        isOpen: r.open
                    })
                });
        }
    }

    dialogClose(choice) {
        if (choice === "book") {
            const time = `${this.state.date}T${this.state.time}Z`;

            this.props.sock.send(JSON.stringify({
                type: "bookRepair",
                cid: this.props.conversation.id,
                rid: this.props.repair,
                time: time
            }));
        }

        this.props.onClose();
    }

    render() {
        return <Dialog open={true} onClose={this.dialogClose}>
            <DialogTitle>Repair book</DialogTitle>
            <DialogContent>
                <div className="RepairBookForm">
                    <TextField label='Date'>
                        <Input type="date" value={this.state.date} onChange={this.updateDate} isValid={this.state.dateValid} required pattern="\d{4}-\d{2}-\d{2}"/>
                    </TextField>
                    <TextField label='Time'>
                        <Input type="time" value={this.state.time} onChange={this.updateTime} isValid={this.state.timeValid} required pattern="\d{2}:\d{2}"/>
                    </TextField>
                </div>
                {this.state.isOpen !== null ? (
                    this.state.isOpen ? null : <div>Not open at that time</div>
                ) : null}
            </DialogContent>
            <DialogFooter>
                <DialogButton action='cancel'>Cancel</DialogButton>
                <DialogButton action='book' isDefault disabled={!this.state.isOpen}>Book</DialogButton>
            </DialogFooter>
        </Dialog>
    }
}

class RepairCard extends Component {
    state = {
        brands: [],
        models: [],
        repairs: [],
        brand: '',
        model: '',
        repair: '',
        repair_m: null,
        book_repair: false,
    };

    constructor(props) {
        super(props);

        // this.canSubmit = this.canSubmit.bind(this);
        this.updateBrand = this.updateBrand.bind(this);
        this.updateModel = this.updateModel.bind(this);
        this.updateRepair = this.updateRepair.bind(this);
        this.getRepairs = this.getRepairs.bind(this);
    }

    componentDidMount() {
        fetch(ROOT_URL + "data/brands/", {
            credentials: "include"
        })
            .then(r => r.json())
            .then(r => {
                this.setState({
                    brands: r
                });
            });
    }


    updateBrand(_, i) {
        let brand = i.getAttribute('data-value');
        this.setState({brand: brand, model: ''});
        fetch(ROOT_URL + "data/models/" + brand + "/", {
            credentials: "include"
        })
            .then(r => r.json())
            .then(r => {
                this.setState({
                    models: r
                });
            });
    }

    getRepairs(model) {
        if (model.length) {
            fetch(ROOT_URL + `data/repairs/${model}`, {
                credentials: "include"
            })
                .then(r => r.json())
                .then(r => {
                    this.setState({
                        repairs: r
                    });
                });
        }
    }

    updateModel(_, i) {
        this.setState({model: i.getAttribute('data-value')});
        this.getRepairs(i.getAttribute('data-value'));
    }

    updateRepair(_, i) {
        this.setState({repair: i.getAttribute('data-value')});
    }

    render() {
        return <div className="RepairCard">
            <div className="RepairForm">
                <Select enhanced label='Brand' value={this.state.brand}
                        onEnhancedChange={this.updateBrand}>
                    {this.state.brands.map((brand, i) =>
                        <Option key={i} value={brand.name}>{brand.display_name}</Option>)}
                </Select>
                <Select enhanced label='Model' value={this.state.model}
                        onEnhancedChange={this.updateModel}>
                    {this.state.models.map((model, i) =>
                        <Option key={i} value={model.id}>{model.display_name}</Option>)}
                </Select>
                <Select enhanced label='Repair' value={this.state.repair}
                        onEnhancedChange={this.updateRepair}>
                    {this.state.repairs.map((repair, i) =>
                        <Option key={i} value={i}>{repair.repair.display_name}</Option>)}
                </Select>
            </div>
            {this.state.repair ? <React.Fragment>
                Cost: &pound;{this.state.repairs[this.state.repair].price},
                Time: {this.state.repairs[this.state.repair].time}
                <br/>
                <Button ripple colored raised onClick={() => this.setState({
                    book_repair: true
                })} disabled={!this.props.conversation.can_message()}>
                    Book
                </Button>
            </React.Fragment> : null}
            {this.state.book_repair ? <RepairBooking
                repair={this.state.repairs[this.state.repair].id} conversation={this.props.conversation}
                    sock={this.props.sock} onClose={() => this.setState({
                    book_repair: false
                })}
            /> : null}
        </div>
    }
}

export default React.forwardRef((props, ref) =>
    <SockContext.Consumer>
        {value => <RepairCard sock={value} ref={ref} {...props}/>}
    </SockContext.Consumer>
);