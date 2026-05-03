return {
  "nvim-treesitter/nvim-treesitter",
  event = { "BufReadPre", "BufNewFile" },
  build = ":TSUpdate",

  config = function()
    require('nvim-treesitter').setup({
      auto_install = true,
      highlight = { enable = true, additional_vim_regex_highlighting = false },
      indent = { enable = true },

      ensure_installed = {
        "lua",
        "python",
        "rust",
        "go",
        "zig",
        "dart",
        "dockerfile",
        "gitignore",
        "json",
        "yaml",
        "toml",
        "vim"
      },

      incremental_selection = {
        enable = true,
        keymaps = {
          init_selection = "<C-Space>",
          node_incremental = "<C-Space>",
          scope_incremental = false,
          node_decremental = "<BS>",
        },
      },
    })

    -- Install parsers
    require('nvim-treesitter').install({
      "lua",
      "python",
      "rust",
      "go",
      "zig",
      "dart",
      "dockerfile",
      "gitignore",
      "json",
      "yaml",
      "toml",
      "vim"
    })
  end,
}
