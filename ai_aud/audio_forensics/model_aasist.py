from __future__ import annotations
import gc
import logging
from pathlib import Path
from typing import List, Tuple, Optional, Union
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from .config import (
    XLSR_MODEL_PATH,
    AASIST_MODEL_PATH,
    SCORE_DIRECTION,
    BATCH_SIZE,
)

logger = logging.getLogger("audio_forensics.model")

# =========================================================================
# W2V2-AASIST Architecture Definition
# Reference: Hemlata Tak et al., Odyssey 2022 (arxiv.org/abs/2202.12233)
# =========================================================================

def _patch_fairseq_omegaconf():
    try:
        import fairseq
        from omegaconf import OmegaConf
        import fairseq.dataclass.utils as dc_utils
        import fairseq.tasks as tasks

        def patched_merge(dc, cfg):
            if cfg is None:
                return dc
            c1 = OmegaConf.create(dc)
            c2 = OmegaConf.create(cfg)
            OmegaConf.set_struct(c1, False)
            OmegaConf.set_struct(c2, False)
            return OmegaConf.merge(c1, c2)

        dc_utils.merge_with_parent = patched_merge
        tasks.merge_with_parent = patched_merge
    except Exception as e:
        logger.warning(f"Failed to patch fairseq dataclass merge: {e}")


class SSLModel(nn.Module):
    def __init__(self, device: torch.device, cp_path: str | Path):
        super(SSLModel, self).__init__()
        _patch_fairseq_omegaconf()
        import fairseq
        cp_str = str(cp_path)
        logger.info(f"Loading wav2vec2 front-end from {cp_str}...")
        model, cfg, task = fairseq.checkpoint_utils.load_model_ensemble_and_task([cp_str])
        self.model = model[0]
        self.device = device
        self.out_dim = 1024

    def extract_feat(self, input_data: torch.Tensor) -> torch.Tensor:
        if next(self.model.parameters()).device != input_data.device \
           or next(self.model.parameters()).dtype != input_data.dtype:
            self.model.to(input_data.device, dtype=input_data.dtype)

        if input_data.ndim == 3:
            input_tmp = input_data[:, :, 0]
        else:
            input_tmp = input_data
        emb = self.model(input_tmp, mask=False, features_only=True)["x"]
        return emb


class GraphAttentionLayer(nn.Module):
    def __init__(self, in_dim: int, out_dim: int, **kwargs):
        super().__init__()
        self.att_proj = nn.Linear(in_dim, out_dim)
        self.att_weight = self._init_new_params(out_dim, 1)
        self.proj_with_att = nn.Linear(in_dim, out_dim)
        self.proj_without_att = nn.Linear(in_dim, out_dim)
        self.bn = nn.BatchNorm1d(out_dim)
        self.input_drop = nn.Dropout(p=0.2)
        self.act = nn.SELU(inplace=True)
        self.temp = kwargs.get("temperature", 1.0)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.input_drop(x)
        att_map = self._derive_att_map(x)
        x = self._project(x, att_map)
        x = self._apply_BN(x)
        x = self.act(x)
        return x

    def _pairwise_mul_nodes(self, x: torch.Tensor) -> torch.Tensor:
        nb_nodes = x.size(1)
        x_exp = x.unsqueeze(2).expand(-1, -1, nb_nodes, -1)
        x_mirror = x_exp.transpose(1, 2)
        return x_exp * x_mirror

    def _derive_att_map(self, x: torch.Tensor) -> torch.Tensor:
        att_map = self._pairwise_mul_nodes(x)
        att_map = torch.tanh(self.att_proj(att_map))
        att_map = torch.matmul(att_map, self.att_weight)
        att_map = att_map / self.temp
        att_map = F.softmax(att_map, dim=-2)
        return att_map

    def _project(self, x: torch.Tensor, att_map: torch.Tensor) -> torch.Tensor:
        x1 = self.proj_with_att(torch.matmul(att_map.squeeze(-1), x))
        x2 = self.proj_without_att(x)
        return x1 + x2

    def _apply_BN(self, x: torch.Tensor) -> torch.Tensor:
        org_size = x.size()
        x = x.view(-1, org_size[-1])
        x = self.bn(x)
        x = x.view(org_size)
        return x

    def _init_new_params(self, *size):
        out = nn.Parameter(torch.FloatTensor(*size))
        nn.init.xavier_normal_(out)
        return out


class HtrgGraphAttentionLayer(nn.Module):
    def __init__(self, in_dim: int, out_dim: int, **kwargs):
        super().__init__()
        self.proj_type1 = nn.Linear(in_dim, in_dim)
        self.proj_type2 = nn.Linear(in_dim, in_dim)
        self.att_proj = nn.Linear(in_dim, out_dim)
        self.att_projM = nn.Linear(in_dim, out_dim)
        self.att_weight11 = self._init_new_params(out_dim, 1)
        self.att_weight22 = self._init_new_params(out_dim, 1)
        self.att_weight12 = self._init_new_params(out_dim, 1)
        self.att_weightM = self._init_new_params(out_dim, 1)
        self.proj_with_att = nn.Linear(in_dim, out_dim)
        self.proj_without_att = nn.Linear(in_dim, out_dim)
        self.proj_with_attM = nn.Linear(in_dim, out_dim)
        self.proj_without_attM = nn.Linear(in_dim, out_dim)
        self.bn = nn.BatchNorm1d(out_dim)
        self.input_drop = nn.Dropout(p=0.2)
        self.act = nn.SELU(inplace=True)
        self.temp = kwargs.get("temperature", 1.0)

    def forward(self, x1: torch.Tensor, x2: torch.Tensor, master: Optional[torch.Tensor] = None):
        num_type1 = x1.size(1)
        num_type2 = x2.size(1)
        x1 = self.proj_type1(x1)
        x2 = self.proj_type2(x2)
        x = torch.cat([x1, x2], dim=1)

        if master is None:
            master = torch.mean(x, dim=1, keepdim=True)
        x = self.input_drop(x)
        att_map = self._derive_att_map(x, num_type1, num_type2)
        master = self._update_master(x, master)
        x = self._project(x, att_map)
        x = self._apply_BN(x)
        x = self.act(x)

        x1_out = x.narrow(1, 0, num_type1)
        x2_out = x.narrow(1, num_type1, num_type2)
        return x1_out, x2_out, master

    def _update_master(self, x: torch.Tensor, master: torch.Tensor) -> torch.Tensor:
        att_map = self._derive_att_map_master(x, master)
        master = self._project_master(x, master, att_map)
        return master

    def _pairwise_mul_nodes(self, x: torch.Tensor) -> torch.Tensor:
        nb_nodes = x.size(1)
        x_exp = x.unsqueeze(2).expand(-1, -1, nb_nodes, -1)
        x_mirror = x_exp.transpose(1, 2)
        return x_exp * x_mirror

    def _derive_att_map_master(self, x: torch.Tensor, master: torch.Tensor) -> torch.Tensor:
        att_map = x * master
        att_map = torch.tanh(self.att_projM(att_map))
        att_map = torch.matmul(att_map, self.att_weightM)
        att_map = att_map / self.temp
        att_map = F.softmax(att_map, dim=-2)
        return att_map

    def _derive_att_map(self, x: torch.Tensor, num_type1: int, num_type2: int) -> torch.Tensor:
        att_map = self._pairwise_mul_nodes(x)
        att_map = torch.tanh(self.att_proj(att_map))
        att_board = torch.zeros_like(att_map[:, :, :, 0]).unsqueeze(-1)
        att_board[:, :num_type1, :num_type1, :] = torch.matmul(
            att_map[:, :num_type1, :num_type1, :], self.att_weight11
        )
        att_board[:, num_type1:, num_type1:, :] = torch.matmul(
            att_map[:, num_type1:, num_type1:, :], self.att_weight22
        )
        att_board[:, :num_type1, num_type1:, :] = torch.matmul(
            att_map[:, :num_type1, num_type1:, :], self.att_weight12
        )
        att_board[:, num_type1:, :num_type1, :] = torch.matmul(
            att_map[:, num_type1:, :num_type1, :], self.att_weight12
        )
        att_map = att_board / self.temp
        att_map = F.softmax(att_map, dim=-2)
        return att_map

    def _project(self, x: torch.Tensor, att_map: torch.Tensor) -> torch.Tensor:
        x1 = self.proj_with_att(torch.matmul(att_map.squeeze(-1), x))
        x2 = self.proj_without_att(x)
        return x1 + x2

    def _project_master(self, x: torch.Tensor, master: torch.Tensor, att_map: torch.Tensor) -> torch.Tensor:
        x1 = self.proj_with_attM(torch.matmul(att_map.squeeze(-1).unsqueeze(1), x))
        x2 = self.proj_without_attM(master)
        return x1 + x2

    def _apply_BN(self, x: torch.Tensor) -> torch.Tensor:
        org_size = x.size()
        x = x.view(-1, org_size[-1])
        x = self.bn(x)
        x = x.view(org_size)
        return x

    def _init_new_params(self, *size):
        out = nn.Parameter(torch.FloatTensor(*size))
        nn.init.xavier_normal_(out)
        return out


class GraphPool(nn.Module):
    def __init__(self, k: float, in_dim: int, p: Union[float, int]):
        super().__init__()
        self.k = k
        self.sigmoid = nn.Sigmoid()
        self.proj = nn.Linear(in_dim, 1)
        self.drop = nn.Dropout(p=p) if p > 0 else nn.Identity()
        self.in_dim = in_dim

    def forward(self, h: torch.Tensor) -> torch.Tensor:
        Z = self.drop(h)
        weights = self.proj(Z)
        scores = self.sigmoid(weights)
        return self.top_k_graph(scores, h, self.k)

    def top_k_graph(self, scores: torch.Tensor, h: torch.Tensor, k: float) -> torch.Tensor:
        _, n_nodes, n_feat = h.size()
        n_nodes = max(int(n_nodes * k), 1)
        _, idx = torch.topk(scores, n_nodes, dim=1)
        idx = idx.expand(-1, -1, n_feat)
        h = h * scores
        h = torch.gather(h, 1, idx)
        return h


class Residual_block(nn.Module):
    def __init__(self, nb_filts: list[int], first: bool = False):
        super().__init__()
        self.first = first
        if not self.first:
            self.bn1 = nn.BatchNorm2d(num_features=nb_filts[0])
        self.conv1 = nn.Conv2d(
            in_channels=nb_filts[0],
            out_channels=nb_filts[1],
            kernel_size=(2, 3),
            padding=(1, 1),
            stride=1,
        )
        self.selu = nn.SELU(inplace=True)
        self.bn2 = nn.BatchNorm2d(num_features=nb_filts[1])
        self.conv2 = nn.Conv2d(
            in_channels=nb_filts[1],
            out_channels=nb_filts[1],
            kernel_size=(2, 3),
            padding=(0, 1),
            stride=1,
        )
        if nb_filts[0] != nb_filts[1]:
            self.downsample = True
            self.conv_downsample = nn.Conv2d(
                in_channels=nb_filts[0],
                out_channels=nb_filts[1],
                padding=(0, 1),
                kernel_size=(1, 3),
                stride=1,
            )
        else:
            self.downsample = False

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        identity = x
        if not self.first:
            out = self.bn1(x)
            out = self.selu(out)
        else:
            out = x

        out = self.conv1(x)
        out = self.bn2(out)
        out = self.selu(out)
        out = self.conv2(out)
        if self.downsample:
            identity = self.conv_downsample(identity)
        out += identity
        return out


class W2V2AASISTModel(nn.Module):
    """
    Exact Model class from TakHemlata/SSL_Anti-spoofing fine-tuned W2V2-AASIST.
    """
    def __init__(self, device: torch.device, xlsr_path: str | Path):
        super().__init__()
        self.device = device

        filts = [128, [1, 32], [32, 32], [32, 64], [64, 64]]
        gat_dims = [64, 32]
        pool_ratios = [0.5, 0.5, 0.5, 0.5]
        temperatures = [2.0, 2.0, 100.0, 100.0]

        self.ssl_model = SSLModel(self.device, cp_path=xlsr_path)
        self.LL = nn.Linear(self.ssl_model.out_dim, 128)

        self.first_bn = nn.BatchNorm2d(num_features=1)
        self.first_bn1 = nn.BatchNorm2d(num_features=64)
        self.drop = nn.Dropout(0.5, inplace=True)
        self.drop_way = nn.Dropout(0.2, inplace=True)
        self.selu = nn.SELU(inplace=True)

        self.encoder = nn.Sequential(
            nn.Sequential(Residual_block(nb_filts=filts[1], first=True)),
            nn.Sequential(Residual_block(nb_filts=filts[2])),
            nn.Sequential(Residual_block(nb_filts=filts[3])),
            nn.Sequential(Residual_block(nb_filts=filts[4])),
            nn.Sequential(Residual_block(nb_filts=filts[4])),
            nn.Sequential(Residual_block(nb_filts=filts[4])),
        )

        self.attention = nn.Sequential(
            nn.Conv2d(64, 128, kernel_size=(1, 1)),
            nn.SELU(inplace=True),
            nn.BatchNorm2d(128),
            nn.Conv2d(128, 64, kernel_size=(1, 1)),
        )

        self.pos_S = nn.Parameter(torch.randn(1, 42, filts[-1][-1]))
        self.master1 = nn.Parameter(torch.randn(1, 1, gat_dims[0]))
        self.master2 = nn.Parameter(torch.randn(1, 1, gat_dims[0]))

        self.GAT_layer_S = GraphAttentionLayer(filts[-1][-1], gat_dims[0], temperature=temperatures[0])
        self.GAT_layer_T = GraphAttentionLayer(filts[-1][-1], gat_dims[0], temperature=temperatures[1])

        self.HtrgGAT_layer_ST11 = HtrgGraphAttentionLayer(gat_dims[0], gat_dims[1], temperature=temperatures[2])
        self.HtrgGAT_layer_ST12 = HtrgGraphAttentionLayer(gat_dims[1], gat_dims[1], temperature=temperatures[2])
        self.HtrgGAT_layer_ST21 = HtrgGraphAttentionLayer(gat_dims[0], gat_dims[1], temperature=temperatures[2])
        self.HtrgGAT_layer_ST22 = HtrgGraphAttentionLayer(gat_dims[1], gat_dims[1], temperature=temperatures[2])

        self.pool_S = GraphPool(pool_ratios[0], gat_dims[0], 0.3)
        self.pool_T = GraphPool(pool_ratios[1], gat_dims[0], 0.3)
        self.pool_hS1 = GraphPool(pool_ratios[2], gat_dims[1], 0.3)
        self.pool_hT1 = GraphPool(pool_ratios[2], gat_dims[1], 0.3)
        self.pool_hS2 = GraphPool(pool_ratios[2], gat_dims[1], 0.3)
        self.pool_hT2 = GraphPool(pool_ratios[2], gat_dims[1], 0.3)

        self.out_layer = nn.Linear(5 * gat_dims[1], 2)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Front-end wav2vec 2.0 feature extraction
        x_ssl_feat = self.ssl_model.extract_feat(x.squeeze(-1))
        x = self.LL(x_ssl_feat)

        x = x.transpose(1, 2)
        x = x.unsqueeze(dim=1)
        x = F.max_pool2d(x, (3, 3))
        x = self.first_bn(x)
        x = self.selu(x)

        x = self.encoder(x)
        x = self.first_bn1(x)
        x = self.selu(x)

        w = self.attention(x)

        w1 = F.softmax(w, dim=-1)
        m = torch.sum(x * w1, dim=-1)
        e_S = m.transpose(1, 2) + self.pos_S

        gat_S = self.GAT_layer_S(e_S)
        out_S = self.pool_S(gat_S)

        w2 = F.softmax(w, dim=-2)
        m1 = torch.sum(x * w2, dim=-2)
        e_T = m1.transpose(1, 2)

        gat_T = self.GAT_layer_T(e_T)
        out_T = self.pool_T(gat_T)

        out_T1, out_S1, master1 = self.HtrgGAT_layer_ST11(out_T, out_S, master=self.master1)
        out_S1 = self.pool_hS1(out_S1)
        out_T1 = self.pool_hT1(out_T1)

        out_T_aug, out_S_aug, master_aug = self.HtrgGAT_layer_ST12(out_T1, out_S1, master=master1)
        out_T1 = out_T1 + out_T_aug
        out_S1 = out_S1 + out_S_aug
        master1 = master1 + master_aug

        out_T2, out_S2, master2 = self.HtrgGAT_layer_ST21(out_T, out_S, master=self.master2)
        out_S2 = self.pool_hS2(out_S2)
        out_T2 = self.pool_hT2(out_T2)

        out_T_aug, out_S_aug, master_aug = self.HtrgGAT_layer_ST22(out_T2, out_S2, master=master2)
        out_T2 = out_T2 + out_T_aug
        out_S2 = out_S2 + out_S_aug
        master2 = master2 + master_aug

        out_T1 = self.drop_way(out_T1)
        out_T2 = self.drop_way(out_T2)
        out_S1 = self.drop_way(out_S1)
        out_S2 = self.drop_way(out_S2)
        master1 = self.drop_way(master1)
        master2 = self.drop_way(master2)

        out_T = torch.max(out_T1, out_T2)
        out_S = torch.max(out_S1, out_S2)
        master = torch.max(master1, master2)

        T_max, _ = torch.max(torch.abs(out_T), dim=1)
        T_avg = torch.mean(out_T, dim=1)
        S_max, _ = torch.max(torch.abs(out_S), dim=1)
        S_avg = torch.mean(out_S, dim=1)

        last_hidden = torch.cat([T_max, T_avg, S_max, S_avg, master.squeeze(1)], dim=1)
        last_hidden = self.drop(last_hidden)
        output = self.out_layer(last_hidden)
        return output


# =========================================================================
# Model Singleton & Scoring Wrapper
# =========================================================================

_MODEL_INSTANCE: Optional[W2V2AASISTModel] = None
_MODEL_DEVICE: Optional[torch.device] = None


def get_torch_device() -> torch.device:
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def check_models_available() -> Tuple[bool, List[str]]:
    missing = []
    if not XLSR_MODEL_PATH.is_file():
        missing.append(f"Base XLS-R checkpoint missing: {XLSR_MODEL_PATH.name}")
    if not AASIST_MODEL_PATH.is_file():
        missing.append(f"AASIST fine-tuned checkpoint missing: {AASIST_MODEL_PATH.name}")
    return len(missing) == 0, missing


def get_model(force_cpu: bool = False) -> Optional[W2V2AASISTModel]:
    global _MODEL_INSTANCE, _MODEL_DEVICE
    if _MODEL_INSTANCE is not None:
        return _MODEL_INSTANCE

    is_avail, missing = check_models_available()
    if not is_avail:
        logger.warning(f"Model checkpoints not found: {missing}")
        return None

    device = torch.device("cpu") if force_cpu else get_torch_device()
    logger.info(f"Initializing W2V2-AASIST model on device: {device}...")

    try:
        model = W2V2AASISTModel(device=device, xlsr_path=XLSR_MODEL_PATH)
        state_dict = torch.load(str(AASIST_MODEL_PATH), map_location=device)
        # Adapt state_dict if wrapped in 'state_dict' or module prefixes
        if isinstance(state_dict, dict) and "state_dict" in state_dict:
            state_dict = state_dict["state_dict"]
        
        # Strip potential 'module.' prefixes
        clean_state_dict = {}
        for k, v in state_dict.items():
            key = k.replace("module.", "")
            clean_state_dict[key] = v

        model.load_state_dict(clean_state_dict, strict=True)
        model.to(device)
        model.eval()

        _MODEL_INSTANCE = model
        _MODEL_DEVICE = device
        logger.info("W2V2-AASIST model successfully loaded.")
        return _MODEL_INSTANCE
    except Exception as e:
        logger.error(f"Failed to instantiate or load W2V2-AASIST model: {e}")
        return None


def score_windows(
    windows: List[np.ndarray],
    batch_size: int = BATCH_SIZE,
    device: Optional[torch.device] = None,
) -> Tuple[np.ndarray, Optional[str]]:
    """
    Scores each 64,600-sample window using W2V2-AASIST.
    Returns:
       (logits_array, error_message)
       Output shape: (N,) float32 array of bona-fide logits (index 1).
       Higher = authentic/genuine, Lower = spoofed/synthetic.
    """
    if not windows:
        return np.zeros(0, dtype=np.float32), "No windows provided for scoring."

    model = get_model()
    if model is None:
        return np.zeros(0, dtype=np.float32), "Model checkpoints are not installed."

    dev = device or _MODEL_DEVICE or get_torch_device()
    results: List[float] = []

    try:
        with torch.no_grad():
            for i in range(0, len(windows), batch_size):
                batch_arrs = windows[i : i + batch_size]
                # Shape: (B, 64600)
                batch_tensor = torch.from_numpy(np.stack(batch_arrs)).float().to(dev)
                # Output logits: (B, 2)
                output = model(batch_tensor)
                # Index 1 = bona-fide logit (higher = more real)
                bona_fide_logits = output[:, 1].detach().cpu().numpy()
                results.extend(bona_fide_logits.tolist())

        return np.array(results, dtype=np.float32), None
    except Exception as e:
        logger.exception("Inference error during window scoring")
        return np.zeros(0, dtype=np.float32), f"Inference failure: {str(e)}"
    finally:
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            gc.collect()
