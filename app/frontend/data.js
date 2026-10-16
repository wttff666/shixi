window.DEMO_DATA = {
  presets: {
    oilTemp: {
      machine: "M001",
      text: "M001 液压油温高报警，运行两个多小时后触发，冷却水进水温度正常",
    },
    barrelTemp: {
      machine: "M004",
      text: "M004 料筒一段温度上不去，制品表面有冷斑，加热指示灯不亮",
    },
    cooling: {
      machine: "M007",
      text: "M007 冷却水流量偏低，进水压力正常，过滤器拆检发现水垢较多",
    },
    cycle: {
      machine: "M016",
      text: "M016 单模周期变长，比平时慢了接近一秒，产量完不成",
    },
    vague: {
      machine: "",
      text: "客户说机器很热，摸起来烫手，说不清是哪个部位，也没看报警画面",
    },
  },
};
