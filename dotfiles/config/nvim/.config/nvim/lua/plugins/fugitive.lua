return {
  "tpope/vim-fugitive",

  config = function()
    local keymap = vim.keymap

    keymap.set("n", "<leader>gs", ":Git<CR>", { noremap = true, silent = true, desc = "Git status" })
    keymap.set("n", "<leader>gd", ":Git diff<CR>", { noremap = true, silent = true, desc = "Git diff" })
    keymap.set("n", "<leader>gaa", ":Git add .<CR>", { noremap = true, silent = true, desc = "Git add all" })
    keymap.set("n", "<leader>gaf", function()
      vim.ui.input({ prompt = "Enter file to git add: " }, function(input)
        if input then
          vim.cmd("Git add " .. input)
        end
      end)
    end, { noremap = true, silent = true, desc = "Git add file" })
    keymap.set("n", "<leader>gc", function()
      vim.ui.input({ prompt = "Enter commit message: " }, function(input)
        if input then
          vim.cmd('Git commit -m "' .. input .. '"')
        end
      end)
    end, { noremap = true, silent = true, desc = "Git commit" })
    keymap.set("n", "<leader>gp", ":Git push<CR>", { noremap = true, silent = true, desc = "Git push" })
  end,
}
