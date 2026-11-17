# das-channel-mapping

[English](README.md) · **中文**

把 DAS（分布式光纤声波传感）光缆的每一道放到地图上，给出经纬度和位置不确定度。陆上、海底、海陆混合的光缆都适用。
它是一个 Claude Code skill，附带的 Python 脚本也能单独运行。

![Kefalonia–Ithaca](docs/kefalonia.png)

## Demo：真实的 Kefalonia–Ithaca 光缆（一分钟）

```bash
git clone https://github.com/WANGYuhan2002/das-channel-mapping && cd das-channel-mapping
pip install -r requirements.txt
python3 examples/kefalonia/run_kefalonia.py
```

这是希腊一条 15 km 的陆–海–陆海底 DAS 光缆（2024 年，1872 道，道距 8.17 m）。demo 读 [`examples/kefalonia/data/`](examples/kefalonia/data/) 里的真实输入：45 个带 GPS 的锤击点、OpenStreetMap 道路、运营商路由、伊萨基手画路线和放道配置。
它先检验锤击记录用的是哪种距离，再建路径和通道表，逐道和当初交付给项目的通道表比较，最后画出上面的图。输出（节选）：

```
1. Distance convention of the shot log: read as the header distance, median -3.9 m, 44/45 within +-21 m;
   read as the label FO_nom, the error grows to -170 m at the beach -> the log uses the header distance
2. Paths between the 43 land anchors: 41 OSM, 1 operator route; OSM vs operator route: median 4 m, p90 14 m
3. Channel map (1872 channels):
    segment  channels  fibre_m  ground_m  pos_unc_min_m  pos_unc_median_m  pos_unc_max_m
      cabin     25-42    144.6      10.5           15.0              15.0           15.0
       land    43-899   7000.3    6432.0            5.1               7.6           14.4
       coil   900-920    171.7       0.0           15.0              15.0           15.0
      beach   921-926     49.6      40.7           15.0              15.0           15.0
        sea  927-1766   6857.7    6724.1           30.0              30.0           30.0
ithaca_land 1767-1871    853.5     831.8           15.0              60.0           60.0
   six slack blocks on land (41, 33, 25, 16, 155 and 131 m of fibre), each at one point of the road
   rebuilt vs delivered table: largest difference 0.76 m (rounding in the 2024 files)
```

重建的表和交付的表最多差 0.76 m，来自 2024 年文件里的取整（经纬度只存 5 位小数，路径约 0.1 m）。每个输入是什么、从哪来，见 [`examples/kefalonia/README.md`](examples/kefalonia/README.md)。锚点、水线和余缆块背后的证据（锤击叠加、海浪频谱、地震、60 天交通）汇总在 [`references/kefalonia-example.md`](das-channel-mapping/references/kefalonia-example.md)。

## 已知真值的检验：合成光缆

```bash
python3 examples/synthetic/run_demo.py
```

demo 先造一条已知真值的合成光缆，共 729 道：一段弯曲的陆上道路（9 个锤击锚点，中间盘着 41 m 余缆）、一个人井盘缆、3 km 海底路由，以及一段没有锚点的对岸。
然后建通道表，逐道和真值比，画出 [`docs/demo.png`](docs/demo.png)，并打印：

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
- **在真实的 15 km 陆–海–陆光缆上验证过**（希腊 Kefalonia–Ithaca，2024；上面的 demo 用真实输入重建了交付的通道表），细节见 [`references/kefalonia-example.md`](das-channel-mapping/references/kefalonia-example.md)：
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

测试：`python3 -m pytest -q tests/`，跑每个脚本和合成 demo，并检查 Kefalonia–Ithaca demo 重建的表与交付的表相差不到 1 m。
Kefalonia–Ithaca 的其他步骤（锤击叠加、地震弱段、水线台阶、车辆定的盘缆点、AIS 检验）在仓库外和原始结果核对过，它们的原始数据不在仓库里。

## 致谢与许可

OpenStreetMap 数据 © OpenStreetMap contributors（ODbL），用 OSM 路径画的图要注明。Kefalonia 图里的海岸线来自 Copernicus GLO-30 DEM（© DLR e.V. 2010–2014 and © Airbus Defence and Space GmbH 2014–2018 provided under COPERNICUS by the European Union and ESA; all rights reserved）。
代码用 MIT 许可，见 [LICENSE](LICENSE)；示例数据的使用条件见 [`examples/kefalonia/README.md`](examples/kefalonia/README.md)。
