from __future__ import print_function
import torch
import torch.utils.data
import torch.nn as nn
import math
from Submodules.utils.utils_dcu import *
import matplotlib.pyplot as plt
import numpy as np

def visualize_tensor(tensor, title="Tensor Visualization", num_channels_to_display=3):
    tensor = tensor.detach().cpu().numpy()
    
    if tensor.ndim == 4:  # Batch, Channels, Height, Width
        tensor = tensor[0]  # Select the first sample in the batch
    
    num_channels = tensor.shape[0]
    
    if num_channels == 1:  # Single-channel image
        tensor = tensor[0]  # Remove channel dimension
        plt.imshow(tensor, cmap='gray')
        plt.title(f"{title} (channel 1)")
        plt.axis('off')
        plt.show()
    elif num_channels == 3:  # RGB image
        tensor = np.transpose(tensor, (1, 2, 0))  # Rearrange dimensions to Height, Width, Channels
        plt.imshow(tensor)
        plt.title(title)
        plt.axis('off')
        plt.show()
    else:
        # Display the first few channels as separate images
        fig, axes = plt.subplots(1, num_channels_to_display, figsize=(15, 5))
        for i in range(min(num_channels, num_channels_to_display)):
            axes[i].imshow(tensor[i], cmap='gray')
            axes[i].set_title(f"{title} (channel {i + 1})")
            axes[i].axis('off')
        plt.show()

class UpProject(nn.Module):

    def __init__(self, in_channels, out_channels, batch_size):
        super(UpProject, self).__init__()
        self.batch_size = batch_size

        self.conv1_1 = nn.Conv2d(in_channels, out_channels, kernel_size=3)
        self.conv1_2 = nn.Conv2d(in_channels, out_channels, kernel_size=(2, 3))
        self.conv1_3 = nn.Conv2d(in_channels, out_channels, kernel_size=(3, 2))
        self.conv1_4 = nn.Conv2d(in_channels, out_channels, kernel_size=2)

        self.conv2_1 = nn.Conv2d(in_channels, out_channels, kernel_size=3)
        self.conv2_2 = nn.Conv2d(in_channels, out_channels, kernel_size=(2, 3))
        self.conv2_3 = nn.Conv2d(in_channels, out_channels, kernel_size=(3, 2))
        self.conv2_4 = nn.Conv2d(in_channels, out_channels, kernel_size=2)

        self.bn1_1 = nn.BatchNorm2d(out_channels)
        self.bn1_2 = nn.BatchNorm2d(out_channels)

        self.relu = nn.ReLU(inplace=True)

        self.conv3 = nn.Conv2d(out_channels, out_channels, 3, padding=1)

        self.bn2 = nn.BatchNorm2d(out_channels)

    def forward(self, x):
        out1_1 = self.conv1_1(nn.functional.pad(x, (1, 1, 1, 1)))

        out1_2 = self.conv1_2(nn.functional.pad(x, (1, 1, 1, 0)))

        out1_3 = self.conv1_3(nn.functional.pad(x, (1, 0, 1, 1)))

        out1_4 = self.conv1_4(nn.functional.pad(x, (1, 0, 1, 0)))

        out2_1 = self.conv2_1(nn.functional.pad(x, (1, 1, 1, 1)))

        out2_2 = self.conv2_2(nn.functional.pad(x, (1, 1, 1, 0)))

        out2_3 = self.conv2_3(nn.functional.pad(x, (1, 0, 1, 1)))

        out2_4 = self.conv2_4(nn.functional.pad(x, (1, 0, 1, 0)))

        height = out1_1.size()[2]
        width = out1_1.size()[3]

        out1_1_2 = torch.stack((out1_1, out1_2), dim=-3).permute(0, 1, 3, 4, 2).contiguous().view(
            self.batch_size, -1, height, width * 2)
        out1_3_4 = torch.stack((out1_3, out1_4), dim=-3).permute(0, 1, 3, 4, 2).contiguous().view(
            self.batch_size, -1, height, width * 2)

        out1_1234 = torch.stack((out1_1_2, out1_3_4), dim=-3).permute(0, 1, 3, 2, 4).contiguous().view(
            self.batch_size, -1, height * 2, width * 2)

        out2_1_2 = torch.stack((out2_1, out2_2), dim=-3).permute(0, 1, 3, 4, 2).contiguous().view(
            self.batch_size, -1, height, width * 2)
        out2_3_4 = torch.stack((out2_3, out2_4), dim=-3).permute(0, 1, 3, 4, 2).contiguous().view(
            self.batch_size, -1, height, width * 2)

        out2_1234 = torch.stack((out2_1_2, out2_3_4), dim=-3).permute(0, 1, 3, 2, 4).contiguous().view(
            self.batch_size, -1, height * 2, width * 2)

        out1 = self.bn1_1(out1_1234)
        out1 = self.relu(out1)
        out1 = self.conv3(out1)
        out1 = self.bn2(out1)

        out2 = self.bn1_2(out2_1234)

        out = out1 + out2
        out = self.relu(out)

        return out

class ResBlock(nn.Module):
    def __init__(self, inplanes, planes, stride):
        super(ResBlock, self).__init__()

        self.conv1 = nn.Sequential(convbn(inplanes, planes, 3, stride),
                                   nn.ReLU(inplace=True))

        self.conv2 = convbn(planes, planes, 3, 1)

        self.ds = convbn(inplanes, planes, 3, stride)

        self.relu = nn.ReLU(inplace=True)

    def forward(self, x):
        out = self.conv1(x)
        out = self.conv2(out)
        x = self.ds(x)
        out += x
        out = self.relu(out)

        return out

class depthCompletionNew_blockN(nn.Module):
    def __init__(self, bs):
        super(depthCompletionNew_blockN, self).__init__()
        self.bs = bs

        self.convS = ResBlock(2, 32, 1)
        self.convS0 = ResBlock(32, 97, 1)
        self.convS1 = ResBlock(97, 193, 2)
        self.convS2 = ResBlock(193, 385, 2)
        self.convS3 = ResBlock(385, 513, 2)
        self.convS4 = ResBlock(513, 512, 2)

        self.conv1 = ResBlock(3, 32, 1)
        self.conv2 = ResBlock(32, 64, 1)
        self.conv3 = ResBlock(64, 128, 2)
        self.conv3_1 = ResBlock(128, 128, 1)
        self.conv4 = ResBlock(128, 256, 2)
        self.conv4_1 = ResBlock(256, 256, 1)
        self.conv5 = ResBlock(256, 256, 2)
        self.conv5_1 = ResBlock(256, 256, 1)
        self.conv6 = ResBlock(256, 512, 2)
        self.conv6_1 = ResBlock(512, 512, 1)

        self.deconv5 = self._make_upproj_layer(UpProject, 512, 256, self.bs)
        self.deconv4 = self._make_upproj_layer(UpProject, 513, 128, self.bs)
        self.deconv3 = self._make_upproj_layer(UpProject, 385, 64, self.bs)
        self.deconv2 = self._make_upproj_layer(UpProject, 193, 32, self.bs)

        self.predict_normal6 = predict_normal(512)
        self.predict_normal5 = predict_normal(513)
        self.predict_normal4 = predict_normal(385)
        self.predict_normal3 = predict_normal(193)
        self.predict_normal2 = predict_normalE2(97)

        self.upsampled_normal6_to_5 = nn.ConvTranspose2d(1, 1, 4, 2, 1, bias=False)
        self.upsampled_normal5_to_4 = nn.ConvTranspose2d(1, 1, 4, 2, 1, bias=False)
        self.upsampled_normal4_to_3 = nn.ConvTranspose2d(1, 1, 4, 2, 1, bias=False)
        self.upsampled_normal3_to_2 = nn.ConvTranspose2d(1, 1, 4, 2, 1, bias=False)

        for m in self.modules():
            if isinstance(m, nn.Conv2d) or isinstance(m, nn.ConvTranspose2d):
                n = m.kernel_size[0] * m.kernel_size[1] * m.out_channels
                m.weight.data.normal_(0, math.sqrt(2. / n))
                if m.bias is not None:
                    m.bias.data.zero_()
            elif isinstance(m, nn.BatchNorm2d):
                m.weight.data.fill_(1)
                m.bias.data.zero_()

    def _make_upproj_layer(self,block,in_channels,out_channels,bs):
        return block(in_channels,out_channels,bs)

    def forward(self, left, sparse2, mask):
        inputM = mask
        inputS = torch.cat((sparse2, inputM), 1)
        inputS_conv = self.convS(inputS)
        input1 = inputS_conv
        inputS_conv0 = self.convS0(input1)
        inputS_conv1 = self.convS1(inputS_conv0)
        inputS_conv2 = self.convS2(inputS_conv1)
        inputS_conv3 = self.convS3(inputS_conv2)
        inputS_conv4 = self.convS4(inputS_conv3)

        input2 = left
        out_conv2 = self.conv2(self.conv1(input2))
        out_conv3 = self.conv3_1(self.conv3(out_conv2))
        out_conv4 = self.conv4_1(self.conv4(out_conv3))
        out_conv5 = self.conv5_1(self.conv5(out_conv4))
        out_conv6 = self.conv6_1(self.conv6(out_conv5))+inputS_conv4

        out6 = self.predict_normal6(out_conv6)
        visualize_tensor(out6, "out6")
        # out6(1,256,32,64)
        normal6_up = self.upsampled_normal6_to_5(out6)
        visualize_tensor(normal6_up, "normal6_up")
        # normal6_up(1,1,32,64)
        out_deconv5 = self.deconv5(out_conv6)
        # out_deconv5(1,256,32,64)

        concat5 = adaptative_cat(out_conv5, out_deconv5, normal6_up)+inputS_conv3
        visualize_tensor(concat5, "concat5")
        # concat5(1,513,32,64)
        out5 = self.predict_normal5(concat5)
        visualize_tensor(out5, "out5")
        # out5(1,1,32,64)
        normal5_up = self.upsampled_normal5_to_4(out5)
        # normal5_up(1,1,64,128)
        out_deconv4 = self.deconv4(concat5)
        # out_deconv5(1,128,64,128)
        concat4 = adaptative_cat(out_conv4, out_deconv4, normal5_up)+inputS_conv2
        visualize_tensor(concat4, "concat4")
        # concat5(1,385,64,128). out_conv5(1,256,64,128). normal5_up(1,1,64,128)
        out4 = self.predict_normal4(concat4)
        visualize_tensor(out4, "out4")
        normal4_up = self.upsampled_normal4_to_3(out4)
        visualize_tensor(normal4_up, "normal4_up")
        out_deconv3 = self.deconv3(concat4)

        concat3 = adaptative_cat(out_conv3, out_deconv3, normal4_up)+inputS_conv1
        visualize_tensor(concat3, "concat3")
        out3 = self.predict_normal3(concat3)
        visualize_tensor(out3, "out3")

        normal3_up = self.upsampled_normal3_to_2(out3)
        visualize_tensor(normal3_up, "normal3_up")
        out_deconv2 = self.deconv2(concat3)

        concat2 = adaptative_cat(out_conv2, out_deconv2, normal3_up)+inputS_conv0
        visualize_tensor(concat2, "concat2")
        # concat2(1,97,256,512)
        out2 = self.predict_normal2(concat2)
        visualize_tensor(out2, "out2")
        # out2(1,2,256,512)
        normal2 = out2
        normal2 = normal2[:,1,:,:]
        normal2 = normal2.unsqueeze(1)
        visualize_tensor(normal2, "normal2")

        return normal2, concat2