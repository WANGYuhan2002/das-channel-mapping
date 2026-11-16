# das-channel-mapping

[English](README.md) · **中文**

一个 Claude Code skill（加一组 Python 脚本），用来做 **DAS 通道映射**：把分布式光纤声波传感（DAS）每一道放到地面的经纬度上，并给出位置不确定度。陆上、海底和海陆混合的光缆都适用。

地图由这几部分组成：

- **锚点**：数据直接把某一道钉在地面某一点的地方——带 GPS 的锤击（敲击）试验，以及由海浪加载定出的水线；
- **锚点之间的路径**：横移到穿过锤点的 OpenStreetMap 道路、运营商路由、用户手画的路线；
- **放道规则**：锚点之间按道号均匀；余缆盘在路上一点；海底路由在两条水线之间拉伸；没有锚点的一端按实测的光纤 / 道路比放；
- **余缆的证据**：每段多出的光纤、地震测耦合（哪些光纤不跟着地面动）、车辆（盘在一点还是沿路铺开、盘在路上哪一点）；
- **不确定度规则**、**独立检验**（锤点 GPS 对路由、AIS 过缆、锤击走时）和**版本化交付**（CSV 表、数据字典、余缆清单、逐道变化表、GeoJSON / KML、md5）。

方法是在希腊 Kefalonia–Ithaca 海底 DAS 光缆（2024）上做出来的，skill 里把它作为示例，保留了真实数字。仓库里不含任何数据和坐标。

## 安装 skill

```bash
git clone https://github.com/WANGYuhan2002/das-channel-mapping
ln -s "$PWD/das-channel-mapping/das-channel-mapping" ~/.claude/skills/das-channel-mapping
```

之后在 Claude Code 里说“做通道映射”“定道位”“看锤击试验”“找余缆 / 盘缆”“定光缆路由”“交付通道表”等（中英文都行），就会用到它。

## 直接用脚本

需要 Python ≥ 3.9 和 numpy、pandas、scipy（OSM 路径要 networkx，测试要 pytest）：

```bash
pip install -r requirements.txt
cd examples/synthetic
python3 make_synthetic.py --out data
python3 ../../das-channel-mapping/scripts/road_path.py --config data/config.json --piece land \
    --osm data/osm.json --reference data/reference_route.csv --out data/paths.csv
python3 ../../das-channel-mapping/scripts/build_channel_map.py data/config.json --out data/out
python3 compare_truth.py data
```

| 脚本 | 做什么 |
|---|---|
| `hammer_anchor.py` | 找每个锤点的锤击、叠加、读锚点道、足迹、小圈和盘缆；检验野外记录用的是哪种距离 |
| `waterline_waves.py` | 用风暴和平静时的海浪功率定水线和沙滩尽头（一道宽的台阶、半升点） |
| `road_path.py` | 锚点之间沿 OSM 道路的最短路，横移到穿过锤点；与参考路由比较后选路 |
| `build_channel_map.py` | 按 JSON 配置（point、line、path、anchored、ratio 几种分段）建通道表 |
| `quake_coupling.py` | 用区域地震找弱耦合段，并和各段多出的光纤对应 |
| `vehicle_coil.py` | 判断是盘在一点还是沿路一段，定盘缆在路上的点（叠加互相关或逐车） |
| `validate_map.py` | 独立检验：GPS 对路由、AIS 过缆、锤击走时 |
| `make_delivery.py` | 数据字典、余缆清单、逐道变化表、GeoJSON / KML、md5 清单 |
| `upload_version.sh` | 把交付包作为一个不可覆盖的版本上传，远端核对 md5，再改 `current` |

每个脚本都有 `--help`。工作流程见 skill 的 `SKILL.md`，方法细节见 `references/`。

## 测试

```bash
python3 -m pytest -q tests/
```

测试用合成数据跑每一个脚本。这些脚本也拿 Kefalonia–Ithaca 的原始结果核对过：通道表、陆上路径、锤击叠加、地震弱段、水线台阶、车辆定的盘缆位置和 AIS 检验都能复现（位置差在原表的取整以内）。

## 致谢

OpenStreetMap 数据 © OpenStreetMap contributors（ODbL）；用 OSM 路径画的图要注明。

## 许可

MIT，见 [LICENSE](LICENSE)。
