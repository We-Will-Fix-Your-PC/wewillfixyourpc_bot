import React, {Component} from 'react';
import Dialog, {DialogButton, DialogContent, DialogFooter, DialogTitle} from '@material/react-dialog';
import TextField, {Input} from '@material/react-text-field';
import Select, {Option} from '@material/react-select';
import {ROOT_URL} from "../App";


const luhn_checksum = (code) => {
    const len = code.length;
    const parity = len % 2;
    let sum = 0;
    for (let i = len - 1; i >= 0; i--) {
        let d = parseInt(code.charAt(i));
        if (i % 2 === parity) {
            d *= 2
        }
        if (d > 9) {
            d -= 9
        }
        sum += d
    }
    return sum % 10
};

export default class UnlockItem extends Component {
    state = {
        networks: [],
        networkMappings: {},
        brands: [],
        models: [],
        network: '',
        brand: '',
        model: '',
        imei: '',
        imeiValid: true,
        unlock: null,
    };

    constructor(props) {
        super(props);

        this.canSubmit = this.canSubmit.bind(this);
        this.updateImei = this.updateImei.bind(this);
        this.updateNetwork = this.updateNetwork.bind(this);
        this.updateBrand = this.updateBrand.bind(this);
        this.updateModel = this.updateModel.bind(this);
        this.dialogClose = this.dialogClose.bind(this);
    }

    componentWillMount() {
        fetch(ROOT_URL + "data/networks/", {
            credentials: "include"
        })
            .then(r => r.json())
            .then(r => {
                let networks = [];
                let networkMappings = {};
                for (let network of r) {
                    networks.push({
                        name: network.name,
                        display_name: network.display_name
                    });
                    networkMappings[network.name] = network.name;
                    let seen_alt_names = [network.display_name];
                    for (let alt_network of network.alternative_names) {
                        if (seen_alt_names.indexOf(alt_network.display_name) === -1) {
                            seen_alt_names.push(alt_network.display_name);
                            networks.push({
                                name: alt_network.name,
                                display_name: `${alt_network.display_name} (${network.display_name})`
                            });
                            networkMappings[alt_network.name] = network.name;
                        }
                    }
                }
                this.setState({
                    networks: networks,
                    networkMappings: networkMappings
                });
            });
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

    canSubmit() {
        if (!this.state.imei.length) {
            return false
        } else if (!this.state.imeiValid) {
            return false;
        } else if (!this.state.unlock) {
            return false;
        }
        return true;
    }

    updateImei(e) {
        let imei = e.target.value;
        let valid = true;

        if (imei.length !== 15) {
            valid = false;
        } else if (isNaN(parseInt(imei))) {
            valid = false;
        } else if (luhn_checksum(imei) !== 0) {
            valid = false;
        }

        this.setState({
            imei: imei,
            imeiValid: valid
        })
    }

    updateNetwork(_, i) {
        this.setState({network: i.getAttribute('data-value'), unlock: null});
        this.getUnlocks(this.state.brand, i.getAttribute('data-value'), this.state.model);
    }

    updateBrand(_, i) {
        let brand = i.getAttribute('data-value');
        this.setState({brand: brand, unlock: null, model: ''});
        fetch(ROOT_URL + "data/models/" + brand + "/", {
            credentials: "include"
        })
            .then(r => r.json())
            .then(r => {
                this.setState({
                    models: r
                });
            });
        this.getUnlocks(brand, this.state.network, this.state.model);
    }

    updateModel(_, i) {
        this.setState({model: i.getAttribute('data-value'), unlock: null});
        this.getUnlocks(this.state.brand, this.state.network, i.getAttribute('data-value'));
    }

    getUnlocks(brand, network, model) {
        if (brand.length && network.length) {
            fetch(ROOT_URL + `data/unlocks/${brand}/${this.state.networkMappings[network]}`, {
                credentials: "include"
            })
                .then(r => r.json())
                .then(r => {
                    if (r.length === 1 && r[0].device === null) {
                        this.setState({
                            unlock: r[0]
                        });
                    } else {
                        for (let unlock of r) {
                            if (unlock.device === model) {
                                this.setState({
                                    unlock: unlock
                                });
                                return;
                            }
                        }
                    }
                });
        }
    }

    dialogClose(choice) {
        if (choice === "add") {
            const data = {
                imei: this.state.imei,
                network: this.state.networkMappings[this.state.network],
                make: this.state.brand,
                model: this.state.model.length ? this.state.model : null,
                days: this.state.unlock.time,
            };
            let network = this.state.networks.filter(n => n.name === this.state.network)[0].display_name;
            let brand = this.state.brands.filter(b => b.name === this.state.brand)[0].display_name;
            let model = this.state.models.filter(m => m.name === this.state.network)[0];
            model = model ? model.display_name : "";
            this.props.onAdd(`Unlock ${brand} ${model} from ${network}`, "unlock", data, this.state.unlock.price);
        }
    }

    render() {
        return <Dialog open={true} onClose={this.dialogClose}>
            <DialogTitle>Phone unlock</DialogTitle>
            <DialogContent>
                <div className="UnlockForm">
                    <Select enhanced label='Network' value={this.state.network}
                            onEnhancedChange={this.updateNetwork}>
                        {this.state.networks.map((network, i) =>
                            <Option key={i} value={network.name}>{network.display_name}</Option>)}
                    </Select>
                    <Select enhanced label='Brand' value={this.state.brand}
                            onEnhancedChange={this.updateBrand}>
                        {this.state.brands.map((brand, i) =>
                            <Option key={i} value={brand.name}>{brand.display_name}</Option>)}
                    </Select>
                    {this.state.models.length ?
                        <Select enhanced label='Model' value={this.state.model}
                                onEnhancedChange={this.updateModel}>
                            {this.state.models.map((model, i) =>
                                <Option key={i} value={model.name}>{model.display_name}</Option>)}
                        </Select> : null}
                    <TextField label='IMEI'>
                        <Input value={this.state.imei} onChange={this.updateImei} isValid={this.state.imeiValid}/>
                    </TextField>
                </div>
                {this.state.unlock ? <div>
                    Cost: {this.state.unlock.price}, Time: {this.state.unlock.time}
                </div> : <div>
                    No unlock available with the selected parameters
                </div>}
            </DialogContent>
            <DialogFooter>
                <DialogButton action='cancel' onClick={this.props.onCancel}>Cancel</DialogButton>
                <DialogButton action='add' isDefault disabled={!this.canSubmit()}>Add</DialogButton>
            </DialogFooter>
        </Dialog>
    }
}