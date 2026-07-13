// testbenches/interface_adapters/sync_fifo_known_good.sv
// Hand-written known-correct synchronous FIFO.
module sync_fifo #(
    parameter WIDTH = 8,
    parameter DEPTH = 4   // must be power of 2
) (
    input  logic clk, rst_n,
    input  logic wr_en, rd_en,
    input  logic [WIDTH-1:0] wr_data,
    output logic [WIDTH-1:0] rd_data,
    output logic full, empty
);
    localparam PTR_W = $clog2(DEPTH);
    logic [WIDTH-1:0] mem [0:DEPTH-1];
    logic [PTR_W:0] wr_ptr, rd_ptr;  // one extra bit to distinguish full/empty

    assign full  = (wr_ptr[PTR_W] != rd_ptr[PTR_W]) &&
                   (wr_ptr[PTR_W-1:0] == rd_ptr[PTR_W-1:0]);
    assign empty = (wr_ptr == rd_ptr);
    assign rd_data = mem[rd_ptr[PTR_W-1:0]];

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            wr_ptr <= 0;
            rd_ptr <= 0;
        end else begin
            if (wr_en && !full) begin
                mem[wr_ptr[PTR_W-1:0]] <= wr_data;
                wr_ptr <= wr_ptr + 1;
            end
            if (rd_en && !empty) begin
                rd_ptr <= rd_ptr + 1;
            end
        end
    end
endmodule
