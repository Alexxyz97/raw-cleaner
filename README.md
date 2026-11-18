# RAW 废片清理工具

用 JPG 选完片、删掉废片之后，一键把对应的 RAW 废片也清理掉。

## 直接使用方法（推荐）

双击 `dist\RAW废片清理工具.exe` 即可运行。**这是单文件绿色版**，拷贝到任意
64 位 Windows 电脑都能直接跑，无需安装 Python 或任何依赖。

界面操作：

1. 点 **选择文件夹…**，选中放照片的那个文件夹。
2. （可选）勾选 **包含子文件夹（递归处理）** —— 默认只处理所选文件夹当前这一层。
3. （可选）勾选 **剔除时移入回收站** —— 默认开启，删除的 RAW 进回收站可还原；
   取消勾选则是永久删除。
4. 二选一：
   - **选出 RAW**：在该文件夹下新建 `待删除RAW` 文件夹，把所有「没有同名 JPG」
     的 RAW 文件移动进去（安全、可反悔）。
   - **剔除 RAW**：直接把所有「没有同名 JPG」的 RAW 文件删除（默认进回收站）。

## 判定规则

- 对每个 RAW 文件，取其主文件名（不含扩展名，忽略大小写）。
- 若同目录里**不存在**相同主名名的 `.jpg` / `.jpeg`，就视为「废片 RAW」。
- 只有 JPG、没有 RAW 的，忽略不管。
- 支持的 RAW 后缀（统称）：
  `arw sr2 srf raw nef nrw cr2 cr3 crw dng raf orf rw2 rwl pef ptx srw x3f gpr
  3fr fff iiq kdc mdc mef mos mrw ori rwz`

## 重新打包

修改了 `raw_cleaner.py` 后，双击 `build_exe.bat` 重新生成 exe
（需本机装有 Python 与 PyInstaller：`pip install pyinstaller`）。

## 文件说明

| 文件 | 作用 |
| --- | --- |
| `dist\RAW废片清理工具.exe` | 最终成品，拷贝即用 |
| `raw_cleaner.py` | 程序源码（纯标准库 tkinter，无第三方依赖） |
| `build_exe.bat` | 一键重新打包脚本 |

## 注意

- 「剔除 RAW」会删除文件，请务必先确认 JPG 已选好片；建议保留默认的
  「移入回收站」，万一删错可从回收站还原。
- 程序在处理前都会弹出确认框并显示将要处理的文件数量。
