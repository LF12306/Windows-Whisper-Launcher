<img width="974" height="196" alt="image" src="https://github.com/user-attachments/assets/2a32f607-9991-4b5a-bf46-3edc0b1cda99" /># Whisper api Launcher

一个用于在 Windows 下快速启动本地部署 Whisper 语音识别api的图形化启动器。


# [魔改版aegisub地址](https://github.com/liuchengwucn/Aegisub)


# 🚀 使用说明
```
python gui_launcher.py
```
或使用 Release 页面提供的exe

## 使用前请确保models文件夹已有ggml-large-v3-turbo.bin或其他模型文件，如需更改要使用的模型请修改py文件中的代码


## 📁 目录结构说明
```
.
├─ bin/
├─ models/
├─ gui_launcher.py
└─ README.md
```
bin/
用于存放程序运行所需的 二进制依赖文件，例如：

Whisper 运行所需的 DLL

CUDA / cuBLAS / ggml 相关库

该目录中的文件是程序运行所必需的。
当前仓库通过 Git LFS 管理这些大体积二进制文件。

感谢[whisper.cpp](https://github.com/ggml-org/whisper.cpp)开源

models/
用于存放语音识别模型文件，例如 Whisper 的各类模型权重。

模型文件体积较大，不方便放在GitHub上

请自行下载
[下载地址](https://huggingface.co/ggerganov/whisper.cpp/tree/main)

使用前请确保对应模型已正确放置在该目录中。


# 📦 Release
如需直接使用的 Windows 可执行版本，请前往 GitHub Releases 页面下载。

## 📄 License

This project is licensed under the MIT License.
