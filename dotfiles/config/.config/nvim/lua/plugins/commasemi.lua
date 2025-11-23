return {
	"saifulapm/commasemi.nvim",
	lazy = false,
	opts = {
		leader = "<localleader>",
		keymaps = true,
		commands = true,
	},
	keys = {
		{ "<localleader>,", desc = "Toggle comma" },
		{ "<localleader>;", desc = "Toggle semicolon" },
		-- { "C-;", desc = "Toggle semicolon" },
		-- { ",", desc = "Toggle comma" },
	},
}
