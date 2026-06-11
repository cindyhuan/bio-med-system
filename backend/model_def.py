import math

import torch
import torch.nn as nn
import torch.nn.functional as F


def load_vnn_masks(mask_path, expected_gene_dim):
    masks = torch.load(mask_path, map_location="cpu", weights_only=False)
    if isinstance(masks, dict) and "masks" in masks:
        masks = masks["masks"]
    masks = [mask.float() for mask in masks]
    if masks[0].shape[1] != expected_gene_dim:
        raise ValueError(
            f"First VNN mask expects {masks[0].shape[1]} genes, "
            f"but cell input has {expected_gene_dim}."
        )
    return masks


class VNNLinear(nn.Module):
    def __init__(self, in_features, out_features, mask, bias=True):
        super().__init__()
        self.in_features = in_features
        self.out_features = out_features
        self.register_buffer("mask", mask.float())
        self.weight = nn.Parameter(torch.empty(out_features, in_features))
        self.bias = nn.Parameter(torch.empty(out_features)) if bias else None
        self.reset_parameters()

    def reset_parameters(self):
        nn.init.kaiming_uniform_(self.weight, a=math.sqrt(5))
        with torch.no_grad():
            self.weight.mul_(self.mask)
        if self.bias is not None:
            bound = 1 / math.sqrt(self.in_features)
            nn.init.uniform_(self.bias, -bound, bound)

    def forward(self, x):
        return F.linear(x, self.weight * self.mask, self.bias)


class PathwayVNNCellEncoder(nn.Module):
    def __init__(self, mask_path, gene_dim=977, output_mode="penultimate", dropout=0.10):
        super().__init__()
        if output_mode not in ["penultimate", "root"]:
            raise ValueError("output_mode must be 'penultimate' or 'root'.")
        self.output_mode = output_mode
        self.masks = load_vnn_masks(mask_path, expected_gene_dim=gene_dim)
        self.layers = nn.ModuleList()
        self.norms = nn.ModuleList()
        for mask in self.masks:
            self.layers.append(VNNLinear(mask.shape[1], mask.shape[0], mask))
            self.norms.append(nn.BatchNorm1d(mask.shape[0]))
        self.dropout = nn.Dropout(dropout)
        self.penultimate_dim = self.masks[-2].shape[0]
        self.root_dim = self.masks[-1].shape[0]
        self.out_dim = self.penultimate_dim if output_mode == "penultimate" else self.root_dim

    def forward(self, cell_expr):
        x = cell_expr
        penultimate = None
        for i, (layer, norm) in enumerate(zip(self.layers, self.norms)):
            x = torch.tanh(layer(x))
            if x.shape[0] > 1 or not self.training:
                x = norm(x)
            x = self.dropout(x)
            if i == len(self.layers) - 2:
                penultimate = x
        return penultimate if self.output_mode == "penultimate" else x

    def forward_all_layers(self, cell_expr):
        x = cell_expr
        activations = []
        for layer, norm in zip(self.layers, self.norms):
            x = torch.tanh(layer(x))
            if x.shape[0] > 1 or not self.training:
                x = norm(x)
            x = self.dropout(x)
            activations.append(x)
        return activations


class MLP(nn.Module):
    def __init__(self, dims, dropout=0.0, final_activation=None):
        super().__init__()
        layers = []
        for i in range(len(dims) - 1):
            layers.append(nn.Linear(dims[i], dims[i + 1]))
            if i < len(dims) - 2:
                layers.append(nn.ReLU())
                if dropout > 0:
                    layers.append(nn.Dropout(dropout))
        if final_activation == "sigmoid":
            layers.append(nn.Sigmoid())
        self.net = nn.Sequential(*layers)

    def forward(self, x):
        return self.net(x)


class DecoDoseNetChemBERTaVNN(nn.Module):
    def __init__(
        self,
        drug_feat_dim=384,
        gene_dim=977,
        hidden_dim=256,
        cell_hidden_dim=256,
        vnn_masks_path="vnn_masks.pt",
        dropout=0.25,
    ):
        super().__init__()
        del hidden_dim, cell_hidden_dim
        self.drug_context_dim = drug_feat_dim
        self.vnn_cell_encoder = PathwayVNNCellEncoder(
            mask_path=vnn_masks_path,
            gene_dim=gene_dim,
            output_mode="penultimate",
            dropout=0.10,
        )
        self.cell_context_dim = self.vnn_cell_encoder.out_dim
        self.theta1_net = MLP(
            [self.drug_context_dim + self.cell_context_dim + 1, 512, 128, 1],
            dropout=dropout,
            final_activation="sigmoid",
        )
        self.theta2_net = MLP(
            [self.drug_context_dim + self.cell_context_dim + 1, 512, 128, 1],
            dropout=dropout,
            final_activation="sigmoid",
        )
        self.epsilon_net = MLP(
            [self.drug_context_dim * 2 + self.cell_context_dim + 2, 512, 128, 1],
            dropout=dropout,
        )
        hpb_in_dim = self.drug_context_dim * 2 + self.cell_context_dim + 2 + 2
        self.hpb_net = MLP(
            [hpb_in_dim, 1024, 512, 128, 1],
            dropout=dropout,
            final_activation="sigmoid",
        )

    def encode_context(self, drugA_feat, drugB_feat, cell_expr):
        z_a = drugA_feat
        z_b = drugB_feat
        z_cell_vnn = self.vnn_cell_encoder(cell_expr)
        return z_a, z_b, z_cell_vnn, z_cell_vnn

    def forward(
        self,
        drugA_feat,
        drugB_feat,
        cell_expr,
        drugA_logconc,
        drugB_logconc,
        single_resp_1,
        single_resp_2,
    ):
        z_a, z_b, z_cell, z_cell_vnn = self.encode_context(drugA_feat, drugB_feat, cell_expr)
        dose_a = drugA_logconc.unsqueeze(1)
        dose_b = drugB_logconc.unsqueeze(1)
        s1 = single_resp_1.unsqueeze(1)
        s2 = single_resp_2.unsqueeze(1)
        theta1_raw = self.theta1_net(torch.cat([z_a, z_cell, dose_a], dim=1))
        theta2_raw = self.theta2_net(torch.cat([z_b, z_cell, dose_b], dim=1))
        denom = theta1_raw + theta2_raw + 1e-8
        theta1 = theta1_raw / denom
        theta2 = theta2_raw / denom
        epsilon = self.epsilon_net(torch.cat([z_a, z_b, z_cell, dose_a, dose_b], dim=1))
        idb_pred = theta1 * s1 + theta2 * s2 + epsilon
        hpb_input = torch.cat([z_a, z_b, z_cell, dose_a, dose_b, s1, s2], dim=1)
        hpb_pred = self.hpb_net(hpb_input)
        return {
            "final_pred": hpb_pred.squeeze(1),
            "hpb_pred": hpb_pred.squeeze(1),
            "idb_pred": idb_pred.squeeze(1),
            "theta1": theta1.squeeze(1),
            "theta2": theta2.squeeze(1),
            "epsilon": epsilon.squeeze(1),
            "alpha": theta1.squeeze(1),
            "beta": theta2.squeeze(1),
            "gamma": epsilon.squeeze(1),
            "single_resp_A": s1.squeeze(1),
            "single_resp_B": s2.squeeze(1),
            "cell_vnn_penultimate": z_cell_vnn,
        }
