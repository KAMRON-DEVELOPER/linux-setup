return {
  "nvim-flutter/flutter-tools.nvim",
  lazy = false,
  dependencies = { "nvim-lua/plenary.nvim" },

  config = function()
    local flutter_tools = require("flutter-tools")

    flutter_tools.setup({
      ui = {
        border = "rounded",
        notification_style = "plugin", -- "native" | "plugin",
      },
      decorations = {
        statusline = {
          app_version = true,
          device = true,
        },
      },
      widget_guides = {
        enabled = true,
      },
      dev_tools = {
        autostart = false,         -- autostart devtools server if not detected
        auto_open_browser = false, -- Automatically opens devtools in the browser
      },
      lsp = {
        color = {         -- show the derived colours for dart variables
          enabled = true, -- whether or not to highlight color variables at all, only supported on flutter >= 2.10
        },
      },
    })

    vim.keymap.set("n", "<leader>FS", ":FlutterRun <CR>", {})
    vim.keymap.set("n", "<leader>FQ", ":FlutterQuit <CR>", {})
    vim.keymap.set("n", "<leader>FR", ":FlutterRestart <CR>", {})
    vim.keymap.set("n", "<leader>LR", ":FlutterLspRestart <CR>", {})
    vim.keymap.set("n", "<leader>FD", ":FlutterDevTools <CR>", {})
  end,
}
