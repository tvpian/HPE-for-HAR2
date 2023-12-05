import torch
import torch.nn as nn
from torch_geometric.data import Batch

from models.transformer import TransformerBinaryClassifier
from models.gcn import PoseGCN


class ActionRecognizer(nn.Module):
    def __init__(
        self,
        gcn_num_features: int,
        gcn_hidden_dim1: int,
        gcn_hidden_dim2: int,
        gcn_output_dim: int,
        transformer_d_model: int,
        transformer_nhead: int,
        transformer_num_layers: int,
        transformer_num_features: int,
        transformer_dropout: float = 0.1,
        transformer_dim_feedforward: int = 2048,
        transformer_num_classes: int = 2,
        is_single_view: bool = True,
    ) -> None:
        """
        Parameters
        ----------
        gcn_num_features : int
            Number of features in the input sequence
        gcn_hidden_dim1 : int
            Dimension of the first hidden layer of the GCN
        gcn_hidden_dim2 : int
            Dimension of the second hidden layer of the GCN
        gcn_output_dim : int
            Dimension of the output layer of the GCN
        transformer_d_model : int
            Dimension of the input embedding
        transformer_nhead : int
            Number of attention heads
        transformer_num_layers : int
            Number of transformer encoder layers
        transformer_num_features : int
            Number of features in the input sequence
        transformer_dropout : float, optional
            Dropout rate, by default 0.1
        transformer_dim_feedforward : int, optional
            Dimension of the feedforward network, by default 2048
        """
        super(ActionRecognizer, self).__init__()
        self.gcn1 = PoseGCN(
            gcn_num_features, gcn_hidden_dim1, gcn_hidden_dim2, gcn_output_dim
        )
        if not is_single_view:
            self.gcn2 = PoseGCN(
                gcn_num_features, gcn_hidden_dim1, gcn_hidden_dim2, gcn_output_dim
            )
            self.gcn3 = PoseGCN(
                gcn_num_features, gcn_hidden_dim1, gcn_hidden_dim2, gcn_output_dim
            )
        self.transformer = TransformerBinaryClassifier(
            transformer_d_model,
            transformer_nhead,
            transformer_num_layers,
            transformer_num_features,
            transformer_dropout,
            transformer_dim_feedforward,
            num_classes=transformer_num_classes,
        )

        # # Self Attention
        # self.self_attention = nn.MultiheadAttention(
        #     embed_dim=gcn_output_dim * 3, num_heads=1
        # )
        # self.projection = nn.Linear(gcn_output_dim * 3, gcn_output_dim)

        # # Linear
        # self.linear = nn.Linear(gcn_output_dim * 3, gcn_output_dim)

        self.is_single_view = is_single_view

    def forward(self, batch: torch.Tensor) -> torch.Tensor:
        """
        Parameters
        ----------
        kps : torch.Tensor
            Input sequence of keypoints

        Returns
        -------
        torch.Tensor
            Classification of the input sequence of keypoints
        """
        outputs = []

        if not self.is_single_view:
            batch_view1 = [Batch.from_data_list(item[0]) for item in batch]
            batch_view2 = [Batch.from_data_list(item[1]) for item in batch]
            batch_view3 = [Batch.from_data_list(item[2]) for item in batch]

            for i in range(len(batch_view1)):
                view1_embedding = self.gcn1(batch_view1[i])
                view2_embedding = self.gcn2(batch_view2[i])
                view3_embedding = self.gcn3(batch_view3[i])

                min_length = min(
                    len(view1_embedding), len(view2_embedding), len(view3_embedding)
                )
                view1_embedding = view1_embedding[:min_length]
                view2_embedding = view2_embedding[:min_length]
                view3_embedding = view3_embedding[:min_length]

                # # Linear
                # output = torch.cat((view1_embedding, view2_embedding, view3_embedding), dim=-1)
                # output = self.linear(output)

                # Average
                output = (view1_embedding + view2_embedding + view3_embedding) / 3

                # # Self Attention
                # concat_emb = torch.cat(
                #     [view1_embedding, view2_embedding, view3_embedding], dim=-1
                # )
                # attention_output, _ = self.self_attention(
                #     concat_emb.unsqueeze(0),
                #     concat_emb.unsqueeze(0),
                #     concat_emb.unsqueeze(0),
                # )
                # output = self.projection(attention_output.squeeze(0))

                output = self.transformer(output.unsqueeze(0).to("cuda"))
                outputs.append(output)
        else:
            batch_view = [Batch.from_data_list(item) for item in batch]

            for i in range(len(batch_view)):
                view_embedding = self.gcn1(batch_view[i])

                output = self.transformer(view_embedding.unsqueeze(0).to("cuda"))
                outputs.append(output)

        return torch.stack(outputs).squeeze(1)
