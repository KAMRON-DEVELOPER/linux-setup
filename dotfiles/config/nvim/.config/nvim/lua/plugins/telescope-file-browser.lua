return {
  "nvim-telescope/telescope-file-browser.nvim",
  dependencies = { "nvim-telescope/telescope.nvim", "nvim-lua/plenary.nvim" },

  config = function()
    local fb_actions = require("telescope._extensions.file_browser.actions")

    require("telescope").setup({
      extensions = {
        file_browser = {
          mappings = {
            ["i"] = {
              ["<A-c>"] = fb_actions.create,
              ["<S-CR>"] = fb_actions.create_from_prompt,
              ["<A-r>"] = fb_actions.rename,
              ["<A-m>"] = fb_actions.move,
              ["<A-y>"] = fb_actions.copy,
              ["<A-d>"] = fb_actions.remove,
              ["<C-o>"] = fb_actions.open,
              ["<C-p>"] = fb_actions.goto_parent_dir,
              ["<C-h>"] = fb_actions.goto_home_dir,
              ["<C-g>"] = fb_actions.goto_cwd,
              ["<C-c>"] = fb_actions.change_cwd,
              ["<C-t>"] = fb_actions.toggle_browser,
              ["<S-h>"] = fb_actions.toggle_hidden,
              ["<S-t>"] = fb_actions.toggle_all,
              ["<bs>"] = fb_actions.backspace,
            },
            ["n"] = {
              ["c"] = fb_actions.create,
              ["r"] = fb_actions.rename,
              ["m"] = fb_actions.move,
              ["y"] = fb_actions.copy,
              ["d"] = fb_actions.remove,
              ["CR"] = fb_actions.open,
              ["C-p"] = fb_actions.goto_parent_dir,
              ["C-h"] = fb_actions.goto_home_dir,
              ["C-g"] = fb_actions.goto_cwd,
              ["C-c"] = fb_actions.change_cwd,
              ["C-t"] = fb_actions.toggle_browser,
              ["S-h"] = fb_actions.toggle_hidden,
              ["S-t"] = fb_actions.toggle_all,
            },
          },
        },
      },
    })

    vim.keymap.set("n", "<space>fb", ":Telescope file_browser<CR>", { desc = "Telescope file browser" })
  end,
}
