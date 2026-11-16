# das-channel-mapping

[English](README.md) · **中文**

把 DAS（分布式光纤声波传感）光缆的每一道放到地图上，给出经纬度和位置不确定度。陆上、海底、海陆混合的光缆都适用。
它是一个 Claude Code skill，附带的 Python 脚本也能单独运行。

![demo](docs/demo.png)

## 一分钟 demo

```bash
git clone https://github.com/WANGYuhan2002/das-channel-mapping && cd das-channel-mapping
pip install -r requirements.txt
python3 examples/synthetic/run_demo.py
```

demo 先造一条已知真值的合成光缆，共 729 道：一段弯曲的陆上道路（9 个锤击锚点，中间盘着 41 m 余缆）、一个人井盘缆、3 km 海底路由，以及一段没有锚点的对岸。
然后建通道表，逐道和真值比，画出上面的图，并打印：

```
          channels  error_median_m  error_max_m  pos_unc_median_m inside_pos_unc
cabin            5             0.7          1.4              15.0           100%
land           281             1.4          3.8               8.3           100%
coil            15             0.0          0.0              15.0           100%
beach            5             0.2          0.3              15.0           100%
sea            372             1.1          1.7              30.0           100%
far_land        41             1.6          1.7              60.0           100%

Segment with the 41 m coil (anchors 5-6, channels 153-192): max error 17 m if the coil is spread evenly,
3.8 m with the coil block (channels 172-176 at one point).
```

这是最好的情况：合成光缆完全符合方法本身的假设。真实光缆的误差大致和 `pos_unc_m` 同量级。

## 地图怎么建

1. **锚点**：数据能把某一道钉在地面某一点的地方，包括带 GPS 的锤击（敲击）点，以及海浪噪声消失处的水线。
2. **锚点之间的路径**：横移到穿过锤点的 OpenStreetMap 道路、运营商路由，或者你手画的路线。
3. **放道**：
   - 锚点之间按道号均匀分布；
   - 余缆盘在路上的一点；
   - 海底路由在两条水线之间拉伸；
   - 没有锚点的一端，按有锚点部分实测的光纤/道路比铺开。
4. **余缆**：多出光纤的段是候选。地震看出哪里的光纤不随地面动，过路车看出这段光纤是不是盘在一点、盘在哪。
5. **不确定度、检验、交付**：
   - 每道按简单规则给 `pos_unc_m`；
   - 用没参与建图的数据检验：锤点 GPS、AIS 过缆、锤击走时；
   - 版本化交付：通道表、数据字典、变化表、GeoJSON / KML、md5。

## 需要什么

| 输入 | 用途 |
|---|---|
| 道数、道距（含光纤长度系数）、文件头起始距离、标距 | 必需 |
| 带 GPS 的锤击试验，或近岸的风暴/平静海浪功率 | 绝对位置 |
| 路由：OSM 道路、运营商图纸或手画路线 | 锚点之间 |
| 5–10 个区域地震、几小时交通、AIS 船迹 | 可选：找余缆、做检验 |

脚本的输入是处理过的数组（包络、频带功率、地震窗口、车辆轨迹），格式见各脚本的 `--help`。**不包括**读取你的解调仪文件和跟踪车辆这两步。

## 在 Claude Code 里用

在仓库目录下运行：

```bash
ln -s "$PWD/das-channel-mapping" ~/.claude/skills/das-channel-mapping
```

之后用中文或英文直接说，比如“用这份锤击记录做通道映射”“#14 和 #15 之间有没有盘缆”“750 道在哪”。
skill 会按 [`SKILL.md`](das-channel-mapping/SKILL.md) 一步步做，需要判断的地方（窗口、阈值、要不要把一块写进图）会先问你。

## 优点

- **每道可追溯**：每道都有位置和不确定度，表里还写明它是由哪段、哪条路径、哪块余缆定的。
- **外业少**：只需一次锤击试验，其余都在记录里（海浪、地震、交通）或者是公开数据（OSM 道路）。
- **能处理余缆**：余缆是陆上最大的单项误差。真实光缆上，一圈 155 m 的盘缆如果均匀摊开，道会偏出最多 56 m；demo 里也能看到同样的效应。
- **独立检验**：GPS、AIS、锤击走时都没参与建图。
- **在真实的 15 km 陆–海–陆光缆上验证过**（希腊 Kefalonia–Ithaca，2024），细节见 [`references/kefalonia-example.md`](das-channel-mapping/references/kefalonia-example.md)：
  - AIS 过缆偏差从旧图的 −279 m 降到 −7 m；
  - 多出光纤超过 30 m 的 5 段，地震在每段里各找到一段弱耦合；其余 37 段一段也没有。

## 局限

- **精度来自锚点**：锚点之间的位置是插值的。`pos_unc_m` 的规则（道路 5–15 m、海里 30 m、无锚点一端 60 m）是从一条光缆总结的经验值，不是拟合出来的误差模型。
- **海里没有锚点**：海底段只是在两条水线之间拉伸。AIS 只能检验大船经过处的整体沿缆偏移；在 Kefalonia–Ithaca 上，中位数是 −7 m，90% 置信区间 −146 到 +26 m。
- **路径是假定的**：光缆如果在两个锚点之间离开道路，只有差得很大时才看得出来（光纤明显比路短）。
- **有的余缆找不到**：只有地震或车辆看得出的余缆才能定位，其余的仍按段均摊。余缆块边界放在哪，要人来判断。
- **车辆只用来定余缆，不用来定普通道**：车在弯道减速，会让位置偏 10–30 m。
- **不是一键流程**：窗口、阈值、哪段弱耦合算盘缆，都要人来定。
- **只在一条真实光缆和合成数据上测过**：埋地、架空、井下或余缆很多的管道光缆都还没测过。

## 脚本

都在 `das-channel-mapping/scripts/` 里，每个都有 `--help`。

| 脚本 | 做什么 |
|---|---|
| `hammer_anchor.py` | 找出并叠加每个锤点的锤击；锚点道、足迹、小圈、盘缆；检验野外记录用的是哪种距离 |
| `waterline_waves.py` | 用风暴和平静时的海浪功率定水线和沙滩尽头 |
| `road_path.py` | 锚点之间沿 OSM 道路走，横移到穿过锤点；和参考路由对比 |
| `build_channel_map.py` | 按 JSON 配置（point、line、path、anchored、ratio）建通道表 |
| `quake_coupling.py` | 用区域地震找弱耦合段，并和每段多出的光纤对应 |
| `vehicle_coil.py` | 判断是盘在一点还是沿路一段，定盘缆在路上的点 |
| `validate_map.py` | 检验：GPS 对路由、AIS 过缆、锤击走时 |
| `make_delivery.py` | 数据字典、余缆清单、变化表、GeoJSON / KML、md5 清单 |
| `upload_version.sh` | 把交付包上传为新版本，在远端核对 md5，再改 `current` |

测试：`python3 -m pytest -q tests/`，用合成数据跑每个脚本和 demo。
脚本也和 Kefalonia–Ithaca 的原始结果核对过；仓库里没有这条光缆的数据和坐标。

## 致谢与许可

OpenStreetMap 数据 © OpenStreetMap contributors（ODbL），用 OSM 路径画的图要注明。MIT 许可，见 [LICENSE](LICENSE)。
